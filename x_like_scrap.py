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
        self.consecutive_invisible_tweets = 0  # Add counter
        self.attempt_count = 0  # Add attempt counter

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
        Get user avatar URL
        :param author_handle: User handle (with @ symbol)
        :return: Avatar URL or None
        """
        try:
            # Build user profile URL
            profile_url = f"https://x.com/{author_handle.replace('@', '')}/photo"
            
            # Use WebDriver to access page
            self.driver.get(profile_url)
            time.sleep(2)  # Wait for page to load
            
            # Find avatar image element
            avatar_img = self.driver.find_element(By.CSS_SELECTOR, "img.css-9pa8cd")
            if avatar_img:
                avatar_url = avatar_img.get_attribute("src")
                if avatar_url:
                    return avatar_url
            
            # Return default avatar if not found
            return "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png"
            
        except Exception as e:
            print(f"Failed to get user avatar: {e}")
            return "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png"

    def scroll_down(self, pixels=500):
        """Scroll down the page"""
        self.driver.execute_script(f"window.scrollBy(0, {pixels});")
        time.sleep(2)  # Wait for content to load

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_fixed(3),
        retry=retry_if_exception_type((TimeoutException, NoSuchElementException, StaleElementReferenceException)),
    )
    def _get_first_tweet(self, timeout=20, use_hacky_workaround_for_reloading_issue=True):
        try:
            # Scroll every 10 attempts
            self.attempt_count += 1
            if self.attempt_count % 100 == 0:
                logger.info("Attempt count reached 100, scrolling down...")
                self.scroll_down()
                time.sleep(3)  # Wait for content to load
                self.attempt_count = 0  # Reset counter

            # Check if page is fully loaded
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except TimeoutException:
                logger.warning("Page load timeout, continuing...")

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
                if self.consecutive_invisible_tweets > 2:  # 3 consecutive invisible posts
                    logger.info("Consecutive invisible posts encountered, attempting to scroll down...")
                    self.scroll_down()
                    self.consecutive_invisible_tweets = 0
                    time.sleep(3)  # Wait for new content to load
                    return self._get_first_tweet()  # Recursive call to try getting new tweet
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
                # Reset counter if tweet is successfully retrieved
                self.consecutive_invisible_tweets = 0
                # If no error message, assume tweet is present
                return self.driver.find_element(
                    By.XPATH, "//article[@data-testid='tweet']"
                )

        except TimeoutException:
            logger.error("Timeout waiting for tweet or after clicking 'Retry'")
            # Try scrolling on timeout
            if self.attempt_count % 100 == 0:
                self.scroll_down()
                time.sleep(3)
            
            # Add pause mechanism
            logger.info("Timeout encountered, please refresh the page manually and press Enter to continue...")
            input("Press Enter to continue...")
            
            raise
        except NoSuchElementException:
            logger.error("Could not find tweet or 'Retry' button")
            # Try scrolling when element not found
            if self.attempt_count % 100 == 0:
                self.scroll_down()
                time.sleep(3)
            
            # Add pause mechanism
            logger.info("Element not found, please refresh the page manually and press Enter to continue...")
            input("Press Enter to continue...")
            
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
            # Try using the passed element first
            try:
                author_name, author_handle, avatar_url = self._extract_author_details(tweet)
                text = self._get_element_text(tweet, ".//div[@data-testid='tweetText']")
            except StaleElementReferenceException:
                # Re-fetch if element is stale
                tweet = WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_element(By.XPATH, "//article[@data-testid='tweet'][1]")
                )
                author_name, author_handle, avatar_url = self._extract_author_details(tweet)
                text = self._get_element_text(tweet, ".//div[@data-testid='tweetText']")
            
            # Get card title
            card_title = self._get_element_text(tweet, "div[data-testid='twitter-article-title']")
            if card_title:
                text = f"{text}\n{card_title}"
            
            data = {
                "text": text,
                "author_name": author_name,
                "author_handle": author_handle,
                "author_avatar": avatar_url,
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
            # If XPath selector
            if selector.startswith(".//"):
                element = parent.find_element(By.XPATH, selector)
            # If CSS selector
            else:
                element = parent.find_element(By.CSS_SELECTOR, selector)
            
            # Get element's innerHTML instead of text
            html = element.get_attribute('innerHTML')
            # Convert <br> tags to newlines
            text = html.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
            # Remove other HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            # Convert HTML entities to normal characters
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
        try:
            # Get author name and handle
            author_details = tweet.find_element(By.XPATH, ".//div[@data-testid='User-Name']").text
            
            # Get author avatar URL
            try:
                avatar_img = tweet.find_element(By.CSS_SELECTOR, "img.css-9pa8cd")
                avatar_url = avatar_img.get_attribute("src")
            except NoSuchElementException:
                avatar_url = "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png"
            
        except:
            author_details = ''
            avatar_url = "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png"

        # Split the string by newline character
        parts = author_details.split("\n")
        if len(parts) >= 2:
            author_name = parts[0]
            author_handle = parts[1]
        else:
            # Fallback in case the format is not as expected
            author_name = author_details
            author_handle = ""

        return author_name, author_handle, avatar_url

    def _get_media_type(self, tweet):
        if tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='videoPlayer']"):
            return "Video"
        if tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetPhoto']"):
            return "Image"
        # Check for images in cards
        if tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='card.layoutLarge.media'] img.css-9pa8cd"):
            return "Image"
        return "No media"

    def _get_images_urls(self, tweet):
        images_urls = []

        # Get video cover image
        video_elements = tweet.find_elements(By.XPATH, ".//video[@poster]")
        for video_element in video_elements:
            poster_url = video_element.get_attribute("poster")
            if poster_url and poster_url not in images_urls:
                images_urls.append(poster_url)

        # Get regular images - using more precise selector
        try:
            # Method 1: Get through data-testid='tweetPhoto'
            photo_divs = tweet.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetPhoto']")
            for photo_div in photo_divs:
                # Try to get img tag
                img = photo_div.find_element(By.TAG_NAME, "img")
                if img:
                    url = img.get_attribute("src")
                    if url and url not in images_urls:
                        images_urls.append(url)
                
                # Try to get background image
                bg_div = photo_div.find_element(By.CSS_SELECTOR, "div[style*='background-image']")
                if bg_div:
                    style = bg_div.get_attribute("style")
                    if "background-image" in style:
                        url = re.search(r'url\("([^"]+)"\)', style)
                        if url and url.group(1) not in images_urls:
                            images_urls.append(url.group(1))
        except:
            pass

        # Get card images
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
            # First try to get from aria-label
            try:
                text = tweet.find_element(
                    By.CSS_SELECTOR, f"button[data-testid='{testid}']"
                ).get_attribute("aria-label")
                numbers = [int(s) for s in re.findall(r"\b\d+\b", text)]
                if numbers:
                    return numbers[0]
            except:
                pass
                
            # If aria-label fails, try to get from button text
            try:
                button = tweet.find_element(
                    By.CSS_SELECTOR, f"button[data-testid='{testid}']"
                )
                # Get button text content
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
            # Get cellInnerDiv to delete
            cell_div = WebDriverWait(self.driver, 10).until(
                lambda d: d.find_element(By.XPATH, "//div[@data-testid='cellInnerDiv'][.//article[@data-testid='tweet'] or .//span[contains(text(),'Age-restricted adult content')] or .//span[contains(text(),'This post is unavailable')]][1]")
            )
            
            # Try to delete 3 times
            for attempt in range(3):
                try:
                    # Execute delete operation
                    self.driver.execute_script("arguments[0].remove();", cell_div)
                    
                    # Check if deletion was successful
                    try:
                        # Get first tweet after deletion
                        new_tweet = WebDriverWait(self.driver, 2).until(
                            lambda d: d.find_element(By.XPATH, "//article[@data-testid='tweet'][1]")
                        )
                        new_url = self._get_tweet_url(new_tweet)
                        
                        # If URL is the same, deletion failed
                        if new_url == current_url:
                            logger.warning(f"Failed to delete tweet, same URL, attempt {attempt + 1}")
                            # Re-fetch cellInnerDiv
                            cell_div = WebDriverWait(self.driver, 10).until(
                                lambda d: d.find_element(By.XPATH, "//div[@data-testid='cellInnerDiv'][.//article[@data-testid='tweet'] or .//span[contains(text(),'Age-restricted adult content')] or .//span[contains(text(),'This post is unavailable')]][1]")
                            )
                            continue
                        else:
                            # Different URL means deletion successful
                            logger.info("Tweet deleted successfully")
                            return
                            
                    except (NoSuchElementException, TimeoutException):
                        # If can't get element, deletion was successful
                        logger.info("Tweet deleted successfully")
                        return
                        
                except StaleElementReferenceException:
                    # If element is stale, re-fetch
                    logger.info('Element may be stale, re-fetching...')
                    cell_div = WebDriverWait(self.driver, 10).until(
                        lambda d: d.find_element(By.XPATH, "//div[@data-testid='cellInnerDiv'][.//article[@data-testid='tweet'] or .//span[contains(text(),'Age-restricted adult content')] or .//span[contains(text(),'This post is unavailable')]][1]")
                    )
                    continue
            
            # If all 3 attempts fail, raise exception
            raise Exception("Failed to delete tweet after 3 attempts")
                
        except (NoSuchElementException, StaleElementReferenceException) as e:
            logger.warning(f"Error deleting tweet: {e}")
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
            # Find link containing view count
            view_link = tweet.find_element(
                By.CSS_SELECTOR, "a[href*='/analytics']"
            )
            # Extract number from aria-label
            aria_label = view_link.get_attribute("aria-label")
            if aria_label:
                # Use regex to extract numbers
                numbers = re.findall(r'\d+', aria_label)
                if numbers:
                    # Convert number string to integer
                    return int(numbers[0])
        except:
            pass
        return 0

    def fetch_tweets(self, page_url, start_date, end_date, method='remove'):
        self.driver.get(page_url)
        cur_filename = f"data/tweets_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        self.consecutive_invisible_tweets = 0  # Reset counter
        processed_urls = set()  # For tracking processed URLs
        tweet_count = 0  # Track number of tweets processed

        # Convert start_date and end_date from "YYYY-MM-DD" to datetime objects
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        while True:
            # Choose method based on tweet count
            if method == 'remove':
                # Use deletion method
                tweet = self._get_first_tweet()
                if not tweet:
                    logger.info("No tweets found, attempting to scroll down...")
                    self.scroll_down(20)
                    time.sleep(0.5)
                    continue

                try:
                    # Get tweet URL
                    url = self._get_tweet_url(tweet)
                    
                    # Skip if URL already processed
                    if url in processed_urls:
                        self._delete_first_tweet(url)
                        continue
                    
                    # Process tweet
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
                            return  # End if date is before start date
                        elif date > end_date:
                            self._delete_first_tweet(url)
                            continue

                    # Save tweet
                    self._save_to_json(row, filename=f"{cur_filename}.jsonl")
                    logger.info(
                        f"Saving tweets...\n{row['date']},  {row['author_name']} -- {row['text'][:50]}...\n\n"
                    )
                    
                    # Record processed URL and increment count
                    processed_urls.add(url)
                    tweet_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing tweet: {e}")
                    continue
                
                # Delete processed tweet
                self._delete_first_tweet(url)
                
            else:
                # Use scrolling method
                tweets = WebDriverWait(self.driver, 10).until(
                    lambda d: d.find_elements(By.XPATH, "//article[@data-testid='tweet']")
                )
                
                # If no tweets found, try scrolling
                if not tweets:
                    logger.info("No tweets found, attempting to scroll down...")
                    self.scroll_down(4000)
                    time.sleep(0.1)
                    continue
                
                # Process each tweet
                for tweet in tweets:
                    try:
                        # Get tweet URL
                        url = self._get_tweet_url(tweet)
                        
                        # Skip if URL already processed
                        if url in processed_urls:
                            continue
                        
                        # Process tweet
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
                                return  # End if date is before start date
                            elif date > end_date:
                                continue  # Skip if date is after end date

                        # Save tweet
                        self._save_to_json(row, filename=f"{cur_filename}.jsonl")
                        logger.info(f"Saving tweets...\n{row['date']},  {row['author_name']} -- {row['text'][:50]}...\n\n")
                        
                        # Record processed URL and increment count
                        processed_urls.add(url)
                        tweet_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing tweet: {e}")
                        continue
                
                # Scroll down
                self.scroll_down(2000)
                time.sleep(0.5)

        # Save to Excel
        self._save_to_excel(json_filename=f"{cur_filename}.jsonl", output_filename=f"{cur_filename}.xlsx")

def get_author_avatar(jsonl_file="data/x.jsonl", output_file="data/author_avatar.jsonl"):
    """
    Read user information from JSONL file, fetch avatars and save them
    :param jsonl_file: Input JSONL file path
    :param output_file: Output JSONL file path
    """
    try:
        # Read all tweet data
        tweets = []
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                tweets.append(json.loads(line.strip()))
        
        # Count author frequency
        author_counts = {}
        for tweet in tweets:
            if 'author_handle' in tweet and tweet['author_handle']:
                handle = tweet['author_handle']
                author_counts[handle] = author_counts.get(handle, 0) + 1
        
        # Sort by frequency
        sorted_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)
        unique_handles = [handle for handle, _ in sorted_authors]
        
        print(f"Found {len(unique_handles)} unique users")
        print("Author frequency statistics (top 10):")
        for handle, count in sorted_authors[:10]:
            print(f"{handle}: {count} times")
        
        # Read existing avatar information
        existing_avatars = {}
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    avatar_data = json.loads(line.strip())
                    # Only keep non-default avatar records
                    if avatar_data['avatar_url'] != "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png":
                        existing_avatars[avatar_data['author_handle']] = avatar_data['avatar_url']
        
        print(f"Found {len(existing_avatars)} users with existing avatars")
        
        # Filter out users with existing avatars
        remaining_handles = [handle for handle in unique_handles if handle not in existing_avatars]
        print(f"Remaining {len(remaining_handles)} users need avatar fetching")
        
        # Create TwitterExtractor instance
        extractor = TwitterExtractor()
        
        # Fetch avatars for remaining users
        new_avatars = []
        for i, handle in enumerate(remaining_handles[:50]):
            try:
                avatar_url = extractor.fetch_user_avatar(handle)
                time.sleep(5)  # Add delay to avoid too frequent requests
                new_avatars.append({
                    'author_handle': handle,
                    'avatar_url': avatar_url
                })
                print(f"{i+1}/{len(remaining_handles)}, Successfully fetched avatar for user {handle} (appears {author_counts[handle]} times)")
            except Exception as e:
                print(f"{i+1}/{len(remaining_handles)}, Failed to fetch avatar for user {handle}: {e}")
                break
        
        # Merge old and new avatar information
        all_avatars = []
        # Add existing avatars
        for handle, url in existing_avatars.items():
            all_avatars.append({
                'author_handle': handle,
                'avatar_url': url
            })
        # Add newly fetched avatars
        all_avatars.extend(new_avatars)
        
        # Save all avatar information to file
        with open(output_file, 'w', encoding='utf-8') as f:
            for avatar in all_avatars:
                json.dump(avatar, f, ensure_ascii=False)
                f.write('\n')
        
        print(f"Avatar information saved to {output_file}")
        print(f"Total of {len(all_avatars)} user avatars saved")
        
    except Exception as e:
        print(f"Error during processing: {e}")


if __name__ == "__main__":

    # Example usage
    # get_author_avatar() # 头像需要单独获取    

    scraper = TwitterExtractor()
    scraper.fetch_tweets(
        "https://twitter.com/tim4sk/likes",
        start_date="2025-01-01",
        end_date="2025-04-10",
        method='remove' # If your likes are less than 1000, use remove
    )
