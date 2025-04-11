import requests
import json
import re
import urllib.parse
import os
from typing import List, Dict
import argparse
from loguru import logger

script_dir = os.path.dirname(os.path.realpath(__file__))
request_details_file = f'{script_dir}{os.sep}RequestDetails.json'
request_details = json.load(open(request_details_file, 'r'))

features, variables = request_details['features'], request_details['variables']
headers = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "accept-encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1"
}


def get_tokens(tweet_url):
    """
    获取Twitter Bearer Token和Guest Token
    """
    # 将x.com转换为twitter.com
    if "x.com" in tweet_url:
        tweet_url = tweet_url.replace("x.com", "twitter.com")

    # 使用默认的Bearer Token
    bearer_token = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

    # 获取guest token
    with requests.Session() as s:
        s.headers.update(headers)
        s.headers.update({"authorization": f"Bearer {bearer_token}"})

        # 激活bearer token并获取guest token
        guest_response = s.post("https://api.twitter.com/1.1/guest/activate.json")
        assert guest_response.status_code == 200, f'Failed to get guest token. Status code: {guest_response.status_code}'
        guest_token = guest_response.json()["guest_token"]

    assert guest_token is not None, f'Failed to get guest token. Tweet url: {tweet_url}'
    return bearer_token, guest_token


def get_details_url(tweet_id, features, variables):
    # create a copy of variables - we don't want to modify the original
    variables = {**variables}
    variables['focalTweetId'] = tweet_id

    return f"https://twitter.com/i/api/graphql/wTXkouwCKcMNQtY-NcDgAA/TweetDetail?variables={urllib.parse.quote(json.dumps(variables))}&features={urllib.parse.quote(json.dumps(features))}"


def get_tweet_details(tweet_url, guest_token, bearer_token):
    """
    获取推文详情
    使用新的API获取推文信息
    """
    tweet_id = re.findall(r'(?<=status/)\d+', tweet_url)
    assert tweet_id is not None and len(
        tweet_id) == 1, f'无法从URL中解析推文ID。请确保使用正确的URL。推文URL: {tweet_url}'
    tweet_id = tweet_id[0]

    # 首先获取页面以获取ct0 token
    session = requests.Session()
    session.headers.update(headers)

    # 访问页面获取cookies
    response = session.get(tweet_url)
    if response.status_code != 200:
        print(f"警告：获取页面失败，状态码: {response.status_code}")

    # 使用新的API端点
    api_url = f"https://twitter.com/i/api/graphql/0hWvDhmW8YQ-S_ib3azIrw/TweetResultByRestId"

    # 准备查询参数
    variables = {
        "tweetId": tweet_id,
        "withCommunity": False,
        "includePromotedContent": False,
        "withVoice": False
    }

    features = {
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "tweetypie_unmention_optimization_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": False,
        "tweet_awards_web_tipping_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "responsive_web_media_download_video_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_enhance_cards_enabled": False
    }

    params = {
        "variables": json.dumps(variables),
        "features": json.dumps(features)
    }

    # 设置请求头
    api_headers = {
        "authorization": f"Bearer {bearer_token}",
        "x-guest-token": guest_token,
        "x-twitter-client-language": "en",
        "x-twitter-active-user": "yes",
        "content-type": "application/json",
    }
    api_headers.update(headers)

    # 发送请求
    details = session.get(api_url, params=params, headers=api_headers)

    if details.status_code != 200:
        print(f"警告：获取推文详情失败，状态码: {details.status_code}")
        print(f"响应内容: {details.text}")
        return None

    # 打印API响应内容
    # print("\nAPI响应内容:")
    # print(details.text)  # 只打印前1000个字符
    # print("...\n")

    return details


def get_tweet_status_id(tweet_url):
    # 将x.com转换为twitter.com
    tweet_url = tweet_url.replace("x.com", "twitter.com")

    sid_patern = r'https://twitter\.com/[^/]+/status/(\d+)'
    if tweet_url[len(tweet_url) - 1] != "/":
        tweet_url = tweet_url + "/"

    match = re.findall(sid_patern, tweet_url)
    if len(match) == 0:
        print("错误：无法从URL中获取推文ID:", tweet_url)
        return None
    status_id = match[0]
    return status_id


def get_associated_media_id(j, tweet_url):
    """
    获取媒体ID
    :param j: 响应对象或文本
    :param tweet_url: 推文URL
    :return: 媒体ID或None
    """
    if hasattr(j, 'text'):
        j = j.text

    sid = get_tweet_status_id(tweet_url)
    if not sid:
        return None

    pattern = r'"expanded_url"[ \t]*:[ \t]*"https://twitter\.com/[^/]+/status/' + sid + r'/[^"]+",[ \t]*"id_str"[ \t]*:[ \t]*"\d+",'
    matches = re.findall(pattern, j)
    if len(matches) > 0:
        target = matches[0]
        target = target[0:len(target) - 1]  # remove the coma at the end
        return json.loads("{" + target + "}")["id_str"]
    return None


def extract_media_info(j, tweet_url, target_all_mp4s=False):
    """
    提取视频URL和封面图URL
    :param j: 响应对象或文本
    :param tweet_url: 推文URL
    :param target_all_mp4s: 是否获取所有视频
    :return: 包含视频URL和封面图URL的字典
    """
    try:
        # 解析JSON响应
        if hasattr(j, 'text'):
            data = json.loads(j.text)
        else:
            data = json.loads(j)

        # print("\n解析的JSON数据:")
        # print(json.dumps(data, indent=2)[:1000])
        # print("...\n")

        # 获取视频信息
        tweet_result = data.get('data', {}).get('tweetResult', {}).get('result', {})
        legacy = tweet_result.get('legacy', {})

        # 检查是否有媒体
        if 'extended_entities' not in legacy:
            print("未找到extended_entities字段")
            return {'videos': []}

        media = legacy['extended_entities'].get('media', [])
        videos = []

        for item in media:
            if item.get('type') == 'video' or item.get('type') == 'animated_gif':
                # 获取封面图
                thumbnail_url = item.get('media_url_https', '')
                if thumbnail_url:
                    thumbnail_url = f"{thumbnail_url}?format=jpg&name=large"

                # 获取视频信息
                variants = item.get('video_info', {}).get('variants', [])
                video_info = {
                    'thumbnail_url': thumbnail_url,
                    'variants': []
                }

                # 获取所有视频变体
                for variant in variants:
                    if variant.get('content_type') == 'video/mp4':
                        video_info['variants'].append({
                            'url': variant.get('url'),
                            'bitrate': variant.get('bitrate', 0),
                            'content_type': variant.get('content_type')
                        })

                # 按比特率排序
                video_info['variants'].sort(key=lambda x: x['bitrate'], reverse=True)
                videos.append(video_info)

        return {'videos': videos}
    except Exception as e:
        print(f"提取媒体信息时出错: {str(e)}")
        return {'videos': []}


def download_parts(url, output_filename):
    resp = requests.get(url, stream=True)

    # container begins with / ends with fmp4 and has a resolution in it we want to capture
    pattern = re.compile(r'(/[^\n]*/(\d+x\d+)/[^\n]*container=fmp4)')

    matches = pattern.findall(resp.text)

    max_res = 0
    max_res_url = None

    for match in matches:
        url, resolution = match
        width, height = resolution.split('x')
        res = int(width) * int(height)
        if res > max_res:
            max_res = res
            max_res_url = url

    assert max_res_url is not None, f'Could not find a url to download from.  Make sure you are using the correct url.  If you are, then file a GitHub issue and copy and paste this message.  Tweet url: {url}'

    video_part_prefix = "https://video.twimg.com"

    resp = requests.get(video_part_prefix + max_res_url, stream=True)

    mp4_pattern = re.compile(r'(/[^\n]*\.mp4)')
    mp4_parts = mp4_pattern.findall(resp.text)

    assert len(
        mp4_parts) == 1, f'There should be exactly 1 mp4 container at this point.  Instead, found {len(mp4_parts)}.  Please open a GitHub issue and copy and paste this message into it.  Tweet url: {url}'

    mp4_url = video_part_prefix + mp4_parts[0]

    m4s_part_pattern = re.compile(r'(/[^\n]*\.m4s)')
    m4s_parts = m4s_part_pattern.findall(resp.text)

    with open(output_filename, 'wb') as f:
        r = requests.get(mp4_url, stream=True)
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
                f.flush()

        for part in m4s_parts:
            part_url = video_part_prefix + part
            r = requests.get(part_url, stream=True)
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()

    return True


def repost_check(j, exclude_replies=True):
    """
    检查是否是转发视频
    :param j: 推文详情
    :param exclude_replies: 是否排除回复
    :return: 原始推文ID或None
    """
    try:
        # 将响应对象转换为文本
        if hasattr(j, 'text'):
            j = j.text

        # 查找原始推文ID
        pattern = r'"source_status_id_str"\s*:\s*"(\d+)"'
        match = re.search(pattern, j)
        if match:
            return match.group(1)
        return None
    except Exception as e:
        print(f"检查转发时出错: {str(e)}")
        return None


def download_video(tweet_url, output_file, target_all_videos=False):
    bearer_token, guest_token = get_tokens(tweet_url)
    resp = get_tweet_details(tweet_url, guest_token, bearer_token)
    mp4s = extract_media_info(resp.text, tweet_url, target_all_mp4s=True)['videos']
    # sometimes there will be multiple mp4s extracted.  This happens when a twitter thread has multiple videos.  What should we do?  Could get all of them, or just the first one.  I think the first one in the list is the one that the user requested... I think that's always true.  We'll just do that and change it if someone complains.
    # names = [output_file.replace('.mp4', f'_{i}.mp4') for i in range(len(mp4s))]

    if target_all_videos:
        video_counter = 1
        original_urls = repost_check(resp.text, exclude_replies=False)

        if len(original_urls) > 0:
            for url in original_urls:
                download_video(url, output_file.replace(".mp4", f"_{video_counter}.mp4"))
                video_counter += 1
            if len(mp4s) > 0:
                for mp4 in mp4s:
                    output_file = output_file.replace(".mp4", f"_{video_counter}.mp4")
                    if "container" in mp4:
                        download_parts(mp4, output_file)

                    else:
                        # use a stream to download the file
                        r = requests.get(mp4, stream=True)
                        with open(output_file, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=1024):
                                if chunk:
                                    f.write(chunk)
                                    f.flush()
                    video_counter += 1
            else:
                original_url = repost_check(resp.text)

        if original_url:
            download_video(original_url, output_file)
        else:
            assert len(
                mp4s) > 0, f'Could not find any mp4s to download.  Make sure you are using the correct url.  If you are, then file a GitHub issue and copy and paste this message.  Tweet url: {tweet_url}'

            mp4 = mp4s[0]
            if "container" in mp4:
                download_parts(mp4, output_file)
            else:
                # use a stream to download the file
                r = requests.get(mp4, stream=True)
                with open(output_file, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                            f.flush()


def get_video_url(tweet_url):
    """
    获取Twitter视频的URL
    :param tweet_url: Twitter视频的URL
    :return: 视频URL列表
    """
    bearer_token, guest_token = get_tokens(tweet_url)
    details = get_tweet_details(tweet_url, guest_token, bearer_token)

    # 检查是否是转发视频
    original_tweet_id = repost_check(details)
    if original_tweet_id:
        tweet_url = f"https://twitter.com/i/status/{original_tweet_id}"
        bearer_token, guest_token = get_tokens(tweet_url)
        details = get_tweet_details(tweet_url, guest_token, bearer_token)

    # 获取视频URL
    video_urls = extract_media_info(details, tweet_url, target_all_mp4s=True)['videos']
    return video_urls


def get_video_info(url: str) -> List[Dict[str, str]]:
    """
    获取推文中的视频信息

    Args:
        url (str): 推文URL

    Returns:
        List[Dict[str, str]]: 视频信息列表，每个元素包含:
            - video_url: 视频URL
            - thumbnail_url: 封面图URL
            - variants: 所有质量选项列表，每个元素包含:
                - bitrate: 比特率
                - resolution: 分辨率
                - url: 视频URL
    """
    try:
        # print("开始获取视频信息...")

        # 获取推文ID
        sid = get_tweet_status_id(url)
        if not sid:
            print("错误：无法获取推文ID")
            return []
        # print(f"成功获取推文ID: {sid}")

        # 获取认证信息
        bearer_token, guest_token = get_tokens(url)
        if not bearer_token or not guest_token:
            print("错误：无法获取认证信息")
            return []
        # print("成功获取认证信息")

        # 获取推文内容
        details = get_tweet_details(url, guest_token, bearer_token)
        if not details:
            print("错误：无法获取推文详情")
            return []
        # print("成功获取推文详情")

        # 使用extract_media_info函数获取视频信息
        media_info = extract_media_info(details, url, target_all_mp4s=True)
        videos = media_info.get('videos', [])

        if not videos:
            print("\n未找到视频信息")
            return []

        # print(f"\n成功获取 {len(videos)} 个视频的信息")

        # 转换为所需的格式
        video_info = []
        for video in videos:
            if video.get('variants'):
                video_info.append({
                    "video_url": video['variants'][0]['url'] if video['variants'] else "",
                    "thumbnail_url": video.get('thumbnail_url', ''),
                    "variants": [
                        {
                            "bitrate": f"{variant['bitrate'] // 1000}kbps",
                            "resolution": re.search(r'/(\d+x\d+)/', variant['url']).group(1) if re.search(
                                r'/(\d+x\d+)/', variant['url']) else "unknown",
                            "url": variant['url']
                        }
                        for variant in video['variants']
                    ]
                })

        return video_info
    except Exception as e:
        print(f"错误：获取视频信息时发生异常: {str(e)}")
        return []


def main():
    parser = argparse.ArgumentParser(description='下载Twitter视频')
    parser.add_argument('url', help='Twitter视频URL')
    parser.add_argument('--url-only', action='store_true', help='只显示视频URL')
    parser.add_argument('--with-thumbnail', action='store_true', help='显示封面图URL')
    parser.add_argument('--all-variants', action='store_true', help='显示所有质量选项')
    args = parser.parse_args()

    video_info = get_video_info(args.url)

    if not video_info:
        print("未找到视频")
        return

    print(f"\n找到 {len(video_info)} 个视频：\n")

    for i, info in enumerate(video_info, 1):
        print(f"视频 {i}:")
        if args.with_thumbnail:
            print(f"封面图URL: {info['thumbnail_url']}")

        if args.all_variants:
            print("所有质量选项：")
            for variant in info['variants']:
                print(f"- {variant['bitrate']} ({variant['resolution']}): {variant['url']}")
        else:
            print(f"视频URL: {info['video_url']}")
        print()


if __name__ == "__main__":

    url = 'https://x.com/aigclink/status/1909792992459936027'
    res = get_video_info(url)
    print(json.dumps(res, indent=2))
    # main()
