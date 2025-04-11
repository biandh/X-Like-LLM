# -*- coding: utf-8 -*-
import traceback

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime, timedelta
import re
import json
import time
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from loguru import logger
from config import TWITTER_AUTH_TOKEN
import requests
from bs4 import BeautifulSoup
import os


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class TwitterExtractor:
    def __init__(self, headless=True):
        self.driver = self._start_chrome(headless)
        self.set_token()
        self.consecutive_invisible_tweets = 0  # 添加计数器
        self.attempt_count = 0  # 添加尝试次数计数器

    def _start_chrome(self, headless):
        options = Options()
        options.headless = headless
        driver = webdriver.Chrome(options=options)
        driver.get("https://twitter.com")
        return driver

    def set_token(self, auth_token=TWITTER_AUTH_TOKEN):
        if not auth_token or auth_token == "YOUR_TWITTER_AUTH_TOKEN_HERE":
            raise ValueError("Access token is missing. Please configure it properly.")
        expiration = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        cookie_script = f"document.cookie = 'auth_token={auth_token}; expires={expiration}; path=/';"
        self.driver.execute_script(cookie_script)
    
    def fetch_user_avatar(self, author_handle):
        """
        获取用户头像 URL
        :param author_handle: 用户 handle（带 @ 符号）
        :return: 头像 URL 或 None
        """
        try:
            # 构建用户主页 URL
            profile_url = f"https://x.com/{author_handle.replace('@', '')}/photo"
            
            # 使用 WebDriver 访问页面
            self.driver.get(profile_url)
            time.sleep(2)  # 等待页面加载
            
            # 查找头像图片元素
            avatar_img = self.driver.find_element(By.CSS_SELECTOR, "img.css-9pa8cd")
            if avatar_img:
                avatar_url = avatar_img.get_attribute("src")
                if avatar_url:
                    return avatar_url
            
            # 如果找不到头像，返回默认头像
            return "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png"
            
        except Exception as e:
            print(f"获取用户头像失败: {e}")
            return "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png"

    def scroll_down(self, pixels=500):
        """向下滚动页面"""
        self.driver.execute_script(f"window.scrollBy(0, {pixels});")
        time.sleep(2)  # 等待内容加载

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_fixed(3),
        retry=retry_if_exception_type((TimeoutException, NoSuchElementException, StaleElementReferenceException)),
    )
    def _get_first_tweet(self, timeout=20, use_hacky_workaround_for_reloading_issue=True):
        try:
            # 每10次尝试才滚动一次
            self.attempt_count += 1
            if self.attempt_count % 100 == 0:
                logger.info("尝试次数达到100次，向下滚动...")
                self.scroll_down()
                time.sleep(3)  # 等待内容加载
                self.attempt_count = 0  # 重置计数器

            # 检查页面是否加载完成
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                logger.warning("页面加载超时，继续尝试...")

            # Wait for either a tweet or the error message to appear
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                or d.find_elements(By.XPATH, "//span[contains(text(),'Try reloading')]")
                or d.find_elements(By.XPATH, "//span[contains(text(),'Something went wrong')]")
            )

            # Check for error message and try to click "Retry" if it's present
            error_message = self.driver.find_elements(
                By.XPATH, "//span[contains(text(),'Try reloading')]"
            )
            if error_message:
                self.consecutive_invisible_tweets += 1
                if self.consecutive_invisible_tweets > 2:  # 连续3次遇到不可见帖子
                    logger.info("连续遇到不可见帖子，尝试向下滚动...")
                    self.scroll_down()
                    self.consecutive_invisible_tweets = 0
                    time.sleep(3)  # 等待新内容加载
                    return self._get_first_tweet()  # 递归调用，尝试获取新的推文
                elif use_hacky_workaround_for_reloading_issue:
                    logger.info(
                        "Encountered 'Something went wrong. Try reloading.' error.\nTrying to resolve with a hacky workaround (click on another tab and switch back). Note that this is not optimal.\n"
                    )
                    logger.info(
                        "You do not have to worry about data duplication though. The save to excel part does the dedup."
                    )
                    self._navigate_tabs()

                    WebDriverWait(self.driver, timeout).until(
                        lambda d: d.find_elements(
                            By.XPATH, "//article[@data-testid='tweet']"
                        )
                    )
                else:
                    raise TimeoutException(
                        "Error message present. Not using hacky workaround."
                    )
            else:
                # 如果成功获取到推文，重置计数器
                self.consecutive_invisible_tweets = 0
                # If no error message, assume tweet is present
                return self.driver.find_element(
                    By.XPATH, "//article[@data-testid='tweet']"
                )

        except TimeoutException:
            logger.error("Timeout waiting for tweet or after clicking 'Retry'")
            # 在超时时也尝试向下滚动
            if self.attempt_count % 100 == 0:
                self.scroll_down()
                time.sleep(3)
            
            # 添加暂停机制
            logger.info("遇到超时，请手动刷新页面后按回车继续...")
            input("按回车继续...")
            
            raise
        except NoSuchElementException:
            logger.error("Could not find tweet or 'Retry' button")
            # 在找不到元素时也尝试向下滚动
            if self.attempt_count % 100 == 0:
                self.scroll_down()
                time.sleep(3)
            
            # 添加暂停机制
            logger.info("找不到元素，请手动刷新页面后按回车继续...")
            input("按回车继续...")
            
            raise

    def _navigate_tabs(self, target_tab="Likes"):
        # Deal with the 'Retry' issue. Not optimal.
        try:
            # Click on the 'Media' tab
            self.driver.find_element(By.XPATH, "//span[text()='Media']").click()
            time.sleep(2)  # Wait for the Media tab to load

            # Click back on the Target tab. If you are fetching posts, you can click on 'Posts' tab
            self.driver.find_element(By.XPATH, f"//span[text()='{target_tab}']").click()
            time.sleep(2)  # Wait for the Likes tab to reload
        except NoSuchElementException as e:
            logger.error("Error navigating tabs: " + str(e))

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_fixed(2),
        retry=retry_if_exception_type((StaleElementReferenceException, NoSuchElementException)),
    )
    def _process_tweet(self, tweet):
        try:
            # 先尝试使用传入的元素
            try:
                author_name, author_handle = self._extract_author_details(tweet)
                text = self._get_element_text(tweet, ".//div[@data-testid='tweetText']")
            except StaleElementReferenceException:
                # 如果元素过时，才重新获取
                tweet = WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_element(By.XPATH, "//article[@data-testid='tweet'][1]")
                )
                author_name, author_handle = self._extract_author_details(tweet)
                text = self._get_element_text(tweet, ".//div[@data-testid='tweetText']")
            
            # 获取卡片标题
            card_title = self._get_element_text(tweet, "div[data-testid='twitter-article-title']")
            if card_title:
                text = f"{text}\n{card_title}"
            
            data = {
                "text": text,
                "author_name": author_name,
                "author_handle": author_handle,
                "date": self._get_element_attribute(tweet, "time", "datetime")[:10],
                "lang": self._get_element_attribute(
                    tweet, "div[data-testid='tweetText']", "lang"
                ),
                "url": self._get_tweet_url(tweet),
                "mentioned_urls": self._get_mentioned_urls(tweet),
                "is_retweet": self.is_retweet(tweet),
                "media_type": self._get_media_type(tweet),
                "images_urls": (self._get_images_urls(tweet) if self._get_media_type(tweet) in ["Image", "Video"] else []),
                "num_views": self._get_view_count(tweet),
            }
            
            # Convert date format
            if data["date"]:
                data["date"] = datetime.strptime(data["date"], "%Y-%m-%d").strftime(
                    "%Y-%m-%d"
                )

            # Extract numbers from aria-labels
            data.update(
                {
                    "num_reply": self._extract_number_from_aria_label(tweet, "reply"),
                    "num_retweet": self._extract_number_from_aria_label(tweet, "retweet"),
                    "num_like": self._extract_number_from_aria_label(tweet, "unlike"),
                }
            )
            return data
        except StaleElementReferenceException:
            logger.warning("Stale element encountered, retrying...")
            raise
        except Exception as e:
            logger.error(f"Error processing tweet: {e}")
            logger.info(f"Tweet: {tweet}")
            raise

    def _get_element_text(self, parent, selector):
        try:
            # 如果是 XPath 选择器
            if selector.startswith(".//"):
                element = parent.find_element(By.XPATH, selector)
            # 如果是 CSS 选择器
            else:
                element = parent.find_element(By.CSS_SELECTOR, selector)
            
            # 获取元素的 innerHTML 而不是 text
            html = element.get_attribute('innerHTML')
            # 将 <br> 标签转换为换行符
            text = html.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
            # 移除其他 HTML 标签
            text = re.sub(r'<[^>]+>', '', text)
            # 将 HTML 实体转换为普通字符
            text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
            return text.strip()
        except NoSuchElementException:
            return ""

    def _get_element_attribute(self, parent, selector, attribute):
        try:
            return parent.find_element(By.CSS_SELECTOR, selector).get_attribute(
                attribute
            )
        except NoSuchElementException:
            return ""

    def _get_mentioned_urls(self, tweet):
        try:
            # Find all 'a' tags that could contain links. You might need to adjust the selector based on actual structure.
            link_elements = tweet.find_elements(
                By.XPATH, ".//a[contains(@href, 'http')]"
            )
            urls = [elem.get_attribute("href") for elem in link_elements]
            return urls
        except NoSuchElementException:
            return []

    def is_retweet(self, tweet):
        try:
            # This is an example; the actual structure might differ.
            retweet_indicator = tweet.find_element(
                By.XPATH, ".//div[contains(text(), 'Retweeted')]"
            )
            if retweet_indicator:
                return True
        except NoSuchElementException:
            return False

    def _get_tweet_url(self, tweet):
        try:
            link_element = tweet.find_element(
                By.XPATH, ".//a[contains(@href, '/status/')]"
            )
            return link_element.get_attribute("href")
        except NoSuchElementException:
            return ""

    def _extract_author_details(self, tweet):
        # author_details = self._get_element_text(
        #     tweet,
        # )
        try:
            author_details = tweet.find_element(By.XPATH, ".//div[@data-testid='User-Name']").text
        except:
            author_details = ''

        # Splitting the string by newline character
        parts = author_details.split("\n")
        if len(parts) >= 2:
            author_name = parts[0]
            author_handle = parts[1]
        else:
            # Fallback in case the format is not as expected
            author_name = author_details
            author_handle = ""

        return author_name, author_handle

    def _get_media_type(self, tweet):
        if tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='videoPlayer']"):
            return "Video"
        if tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetPhoto']"):
            return "Image"
        # 检查卡片中的图片
        if tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='card.layoutLarge.media'] img.css-9pa8cd"):
            return "Image"
        return "No media"

    def _get_images_urls(self, tweet):
        images_urls = []

        # 获取视频封面图
        video_elements = tweet.find_elements(By.XPATH, ".//video[@poster]")
        for video_element in video_elements:
            poster_url = video_element.get_attribute("poster")
            if poster_url and poster_url not in images_urls:
                images_urls.append(poster_url)

        # 获取普通图片 - 使用更精确的选择器
        try:
            # 方法1：通过 data-testid='tweetPhoto' 获取
            photo_divs = tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetPhoto']")
            for photo_div in photo_divs:
                # 尝试获取 img 标签
                img = photo_div.find_element(By.TAG_NAME, "img")
                if img:
                    url = img.get_attribute("src")
                    if url and url not in images_urls:
                        images_urls.append(url)
                
                # 尝试获取背景图片
                bg_div = photo_div.find_element(By.CSS_SELECTOR, "div[style*='background-image']")
                if bg_div:
                    style = bg_div.get_attribute("style")
                    if "background-image" in style:
                        url = re.search(r'url\("([^"]+)"\)', style)
                        if url and url.group(1) not in images_urls:
                            images_urls.append(url.group(1))
        except:
            pass

        # 获取卡片图片
        try:
            card_images = tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='card.layoutLarge.media'] img.css-9pa8cd")
            for card_image in card_images:
                url = card_image.get_attribute("src")
                if url and url not in images_urls:
                    images_urls.append(url)
        except:
            pass
                
        return images_urls

    def _extract_number_from_aria_label(self, tweet, testid):
        try:
            # 首先尝试从 aria-label 获取
            try:
                text = tweet.find_element(
                    By.CSS_SELECTOR, f"button[data-testid='{testid}']"
                ).get_attribute("aria-label")
                numbers = [int(s) for s in re.findall(r"\b\d+\b", text)]
                if numbers:
                    return numbers[0]
            except:
                pass
                
            # 如果 aria-label 获取失败，尝试从按钮内的文本获取
            try:
                button = tweet.find_element(
                    By.CSS_SELECTOR, f"button[data-testid='{testid}']"
                )
                # 获取按钮内的文本内容
                text = button.text
                numbers = [int(s) for s in re.findall(r"\b\d+\b", text)]
                return numbers[0] if numbers else 0
            except:
                pass
                
            return 0
        except:
            return 0

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def _delete_first_tweet(self, current_url):
        try:
            # 获取要删除的 cellInnerDiv
            cell_div = WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(By.XPATH, "//div[@data-testid='cellInnerDiv'][.//article[@data-testid='tweet'] or .//span[contains(text(),'受年龄限制的成人内容')] or .//span[contains(text(),'这个帖子不可用')]][1]")
            )
            
            # 尝试删除3次
            for attempt in range(3):
                try:
                    # 执行删除操作
                    self.driver.execute_script("arguments[0].remove();", cell_div)
                    # time.sleep(0.1 * (2**attempt))  # 等待删除操作完成
                    
                    # 检查是否删除成功
                    try:
                        # 获取删除后的第一个推文
                        new_tweet = WebDriverWait(self.driver, 2).until(
                            lambda d: d.find_element(By.XPATH, "//article[@data-testid='tweet'][1]")
                        )
                        new_url = self._get_tweet_url(new_tweet)
                        
                        # 如果 URL 相同，说明删除失败
                        if new_url == current_url:
                            logger.warning(f"删除推文失败，URL 相同，尝试第 {attempt + 1} 次")
                            # 重新获取 cellInnerDiv
                            cell_div = WebDriverWait(self.driver, 10).until(
                                lambda d: d.find_element(By.XPATH, "//div[@data-testid='cellInnerDiv'][.//article[@data-testid='tweet'] or .//span[contains(text(),'受年龄限制的成人内容')] or .//span[contains(text(),'这个帖子不可用')]][1]")
                            )
                            continue
                        else:
                            # URL 不同，说明删除成功
                            logger.info("推文删除成功")
                            return
                            
                    except (NoSuchElementException, TimeoutException):
                        # 获取不到说明删除成功
                        logger.info("推文删除成功")
                        return
                        
                except StaleElementReferenceException:
                    # 如果元素过时，重新获取
                    logger.info('元素可能过时，重新获取....')
                    cell_div = WebDriverWait(self.driver, 10).until(
                        lambda d: d.find_element(By.XPATH, "//div[@data-testid='cellInnerDiv'][.//article[@data-testid='tweet'] or .//span[contains(text(),'受年龄限制的成人内容')] or .//span[contains(text(),'这个帖子不可用')]][1]")
                    )
                    continue
            
            # 如果3次都失败，抛出异常
            raise Exception("删除推文失败，已尝试3次")
                
        except (NoSuchElementException, StaleElementReferenceException) as e:
            logger.warning(f"删除推文时出错: {e}")
            return

    @staticmethod
    def _save_to_json(data, filename="data.json"):
        with open(filename, "a", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False)
            file.write("\n")

    @staticmethod
    def _save_to_excel(json_filename, output_filename="data/data.xlsx"):
        # Read JSON data
        cur_df = pd.read_json(json_filename, lines=True)

        # Drop duplicates & save to Excel
        cur_df.drop_duplicates(subset=["url"], inplace=True)
        cur_df.to_excel(output_filename, index=False)
        logger.info(
            f"\n\nDone saving to {output_filename}. Total of {len(cur_df)} unique tweets."
        )

    def _get_view_count(self, tweet):
        try:
            # 查找包含查看次数的链接
            view_link = tweet.find_element(
                By.CSS_SELECTOR, "a[href*='/analytics']"
            )
            # 从 aria-label 中提取数字
            aria_label = view_link.get_attribute("aria-label")
            if aria_label:
                # 使用正则表达式提取数字
                numbers = re.findall(r'\d+', aria_label)
                if numbers:
                    # 将数字字符串转换为整数
                    return int(numbers[0])
        except:
            pass
        return 0

    def fetch_tweets(self, page_url, start_date, end_date, method='remove'):
        self.driver.get(page_url)
        cur_filename = f"data/tweets_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        self.consecutive_invisible_tweets = 0  # 重置计数器
        processed_urls = set()  # 用于记录已处理的 URL
        tweet_count = 0  # 记录已获取的帖子数量

        # Convert start_date and end_date from "YYYY-MM-DD" to datetime objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        while True:
            # 根据已获取的帖子数量决定使用哪种方式
            if method == 'remove':
                # 使用删除方式
                tweet = self._get_first_tweet()
                if not tweet:
                    logger.info("未获取到推文，尝试向下滚动...")
                    self.scroll_down(20)
                    time.sleep(0.5)
                    continue

                try:
                    # 获取推文 URL
                    url = self._get_tweet_url(tweet)
                    
                    # 如果 URL 已处理过，跳过
                    if url in processed_urls:
                        self._delete_first_tweet(url)
                        continue
                    
                    # 处理推文
                    row = self._process_tweet(tweet)
                    if row["date"]:
                        try:
                            date = datetime.strptime(row["date"], "%Y-%m-%d")
                        except ValueError as e:
                            logger.info(
                                f"Value error on date format, trying another format.{row['date']}",
                                e,
                            )
                            date = datetime.strptime(row["date"], "%d/%m/%Y")

                        if date < start_date:
                            return  # 如果日期早于开始日期，结束程序
                        elif date > end_date:
                            self._delete_first_tweet(url)
                            continue

                    # 保存推文
                    self._save_to_json(row, filename=f"{cur_filename}.jsonl")
                    logger.info(
                        f"Saving tweets...\n{row['date']},  {row['author_name']} -- {row['text'][:50]}...\n\n"
                    )
                    
                    # 记录已处理的 URL 和增加计数
                    processed_urls.add(url)
                    tweet_count += 1
                    
                except Exception as e:
                    logger.error(f"处理推文时出错: {e}")
                    continue
                
                # 删除已处理的推文
                self._delete_first_tweet(url)
                
            else:
                # 使用滚动方式
                tweets = WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                )
                
                # 如果没有推文，尝试向下滚动
                if not tweets:
                    logger.info("未获取到推文，尝试向下滚动...")
                    self.scroll_down(4000)
                    time.sleep(0.1)
                    continue
                
                # 处理每个推文
                for tweet in tweets:
                    try:
                        # 获取推文 URL
                        url = self._get_tweet_url(tweet)
                        
                        # 如果 URL 已处理过，跳过
                        if url in processed_urls:
                            continue
                        
                        # 处理推文
                        row = self._process_tweet(tweet)
                        if row["date"]:
                            try:
                                date = datetime.strptime(row["date"], "%Y-%m-%d")
                            except ValueError as e:
                                logger.info(
                                    f"Value error on date format, trying another format.{row['date']}",
                                    e,
                                )
                                date = datetime.strptime(row["date"], "%d/%m/%Y")

                            if date < start_date:
                                return  # 如果日期早于开始日期，结束程序
                            elif date > end_date:
                                continue  # 如果日期晚于结束日期，跳过

                        # 保存推文
                        self._save_to_json(row, filename=f"{cur_filename}.jsonl")
                        logger.info(f"Saving tweets...\n{row['date']},  {row['author_name']} -- {row['text'][:50]}...\n\n")
                        
                        # 记录已处理的 URL 和增加计数
                        processed_urls.add(url)
                        tweet_count += 1
                        
                    except Exception as e:
                        logger.error(f"处理推文时出错: {e}")
                        continue
                
                # 向下滚动
                self.scroll_down(2000)
                time.sleep(0.5)

        # Save to Excel
        self._save_to_excel(json_filename=f"{cur_filename}.jsonl", output_filename=f"{cur_filename}.xlsx")

def get_author_avatar(jsonl_file="data/x.jsonl", output_file="data/author_avatar.jsonl"):
    """
    从 JSONL 文件中读取用户信息，获取头像并保存
    :param jsonl_file: 输入的 JSONL 文件路径
    :param output_file: 输出的 JSONL 文件路径
    """
    try:
        # 读取所有推文数据
        tweets = []
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                tweets.append(json.loads(line.strip()))
        
        # 统计作者出现频次
        author_counts = {}
        for tweet in tweets:
            if 'author_handle' in tweet and tweet['author_handle']:
                handle = tweet['author_handle']
                author_counts[handle] = author_counts.get(handle, 0) + 1
        
        # 按频次排序
        sorted_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
        unique_handles = [handle for handle, _ in sorted_authors]
        
        print(f"找到 {len(unique_handles)} 个唯一用户")
        print("作者频次统计（前10名）：")
        for handle, count in sorted_authors[:10]:
            print(f"{handle}: {count} 次")
        
        # 读取已保存的头像信息
        existing_avatars = {}
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    avatar_data = json.loads(line.strip())
                    # 只保留非默认头像的记录
                    if avatar_data['avatar_url'] != "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png":
                        existing_avatars[avatar_data['author_handle']] = avatar_data['avatar_url']
        
        print(f"已找到 {len(existing_avatars)} 个已有头像的用户")
        
        # 过滤掉已有头像的用户
        remaining_handles = [handle for handle in unique_handles if handle not in existing_avatars]
        print(f"剩余 {len(remaining_handles)} 个用户需要获取头像")
        
        # 创建 TwitterExtractor 实例
        extractor = TwitterExtractor()
        
        # 获取剩余用户的头像
        new_avatars = []
        for i, handle in enumerate(remaining_handles[:50]):
            try:
                avatar_url = extractor.fetch_user_avatar(handle)
                time.sleep(5)  # 添加延迟，避免请求过于频繁
                new_avatars.append({
                    'author_handle': handle,
                    'avatar_url': avatar_url
                })
                print(f"{i+1}/{len(remaining_handles)}, 成功获取用户 {handle} 的头像 (出现 {author_counts[handle]} 次)")
            except Exception as e:
                print(f"{i+1}/{len(remaining_handles)}, 获取用户 {handle} 的头像失败: {e}")
                break
        
        # 合并新旧头像信息
        all_avatars = []
        # 添加已有头像
        for handle, url in existing_avatars.items():
            all_avatars.append({
                'author_handle': handle,
                'avatar_url': url
            })
        # 添加新获取的头像
        all_avatars.extend(new_avatars)
        
        # 保存所有头像信息到文件
        with open(output_file, 'w', encoding='utf-8') as f:
            for avatar in all_avatars:
                json.dump(avatar, f, ensure_ascii=False)
                f.write('\n')
        
        print(f"头像信息已保存到 {output_file}")
        print(f"总计保存了 {len(all_avatars)} 个用户的头像信息")
        
    except Exception as e:
        print(f"处理过程中发生错误: {e}")


if __name__ == "__main__":

    # 示例用法
    # get_author_avatar()

    scraper = TwitterExtractor()
    scraper.fetch_tweets(
        "https://twitter.com/tim4sk/likes",
        start_date="2022-01-01",
        end_date="2025-04-10",
        method='remove' # 如果你的喜欢贴上数量少于1000个，使用remove
    )
