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
import logging
from config import TWITTER_AUTH_TOKEN
import requests
from bs4 import BeautifulSoup
import os


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class TwitterExtractor:
    def __init__(self, headless=True):
        self.driver = self._start_chrome(headless)
        self.set_token()

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

    def fetch_tweets(self, page_url, start_date, end_date):
        self.driver.get(page_url)
        cur_filename = f"data/tweets_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

        # Convert start_date and end_date from "YYYY-MM-DD" to datetime objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        while True:
            tweet = self._get_first_tweet()
            if not tweet:
                continue

            row = self._process_tweet(tweet)
            if row["date"]:
                try:
                    date = datetime.strptime(row["date"], "%Y-%m-%d")

                except ValueError as e:
                    # infer date format
                    logger.info(
                        f"Value error on date format, trying another format.{row['date']}",
                        e,
                    )
                    date = datetime.strptime(row["date"], "%d/%m/%Y")

                if date < start_date:
                    break
                elif date > end_date:
                    self._delete_first_tweet()
                    continue

            self._save_to_json(row, filename=f"{cur_filename}.jsonl")
            logger.info(
                f"Saving tweets...\n{row['date']},  {row['author_name']} -- {row['text'][:50]}...\n\n"
            )
            self._delete_first_tweet()

        # Save to Excel
        self._save_to_excel(
            json_filename=f"{cur_filename}.jsonl", output_filename=f"{cur_filename}.xlsx"
        )

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_fixed(2),
        retry=retry_if_exception_type((TimeoutException, NoSuchElementException, StaleElementReferenceException)),
    )
    def _get_first_tweet(
        self, timeout=10, use_hacky_workaround_for_reloading_issue=True
    ):
        try:
            # Wait for either a tweet or the error message to appear
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                or d.find_elements(By.XPATH, "//span[contains(text(),'Try reloading')]")
            )

            # Check for error message and try to click "Retry" if it's present
            error_message = self.driver.find_elements(
                By.XPATH, "//span[contains(text(),'Try reloading')]"
            )
            if error_message and use_hacky_workaround_for_reloading_issue:
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
            elif error_message and not use_hacky_workaround_for_reloading_issue:
                raise TimeoutException(
                    "Error message present. Not using hacky workaround."
                )

            else:
                # If no error message, assume tweet is present
                return self.driver.find_element(
                    By.XPATH, "//article[@data-testid='tweet']"
                )

        except TimeoutException:
            logger.error("Timeout waiting for tweet or after clicking 'Retry'")
            raise
        except NoSuchElementException:
            logger.error("Could not find tweet or 'Retry' button")
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

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def _process_tweet(self, tweet):
        try:
            # 重新获取元素，避免 stale element 问题
            tweet = self.driver.find_element(
                By.XPATH, "//article[@data-testid='tweet']"
            )
            
            author_name, author_handle = self._extract_author_details(tweet)
            
            # 获取推文文本
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

    def _delete_first_tweet(self, sleep_time_range_ms=(0, 1000)):
        try:
            tweet = self.driver.find_element(
                By.XPATH, "//article[@data-testid='tweet'][1]"
            )
            self.driver.execute_script("arguments[0].remove();", tweet)
        except NoSuchElementException:
            logger.info("Could not find the first tweet to delete.")

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
        start_date="2025-01-01",
        end_date="2025-04-09",
    )  # YYYY-MM-DD format
