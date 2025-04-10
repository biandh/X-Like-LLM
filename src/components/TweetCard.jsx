import { FaHeart, FaRetweet, FaComment, FaExternalLinkAlt } from 'react-icons/fa';

function TweetCard({ tweet, avatarMap }) {
  const {
    text,
    author_name,
    author_handle,
    date,
    media_type,
    images_urls,
    num_like,
    num_retweet,
    num_reply,
    num_views,
  } = tweet;

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatNumber = (num) => {
    if (num >= 1000000) {
      const m = Math.floor(num / 1000000);
      const k = Math.floor((num % 1000000) / 100000);
      return k > 0 ? `${m}.${k}M` : `${m}M`;
    } else if (num >= 10000) {
      const w = Math.floor(num / 10000);
      const k = Math.floor((num % 10000) / 1000);
      return k > 0 ? `${w}.${k}w` : `${w}w`;
    }
    return num.toString();
  };

  let cardStyle = '';
  let mediaStyle = '';
  let textStyle = '';

  if (media_type === 'Image') {
    cardStyle = 'bg-[#15202b] border border-gray-700';
    mediaStyle = 'bg-[#1a2734]';
    textStyle = 'text-white';
  } else if (media_type === 'Video') {
    cardStyle = 'bg-[#15202b] border border-gray-700';
    mediaStyle = 'bg-[#1a2734]';
    textStyle = 'text-white';
  } else {
    cardStyle = 'bg-[#15202b] border border-gray-700';
    mediaStyle = 'bg-[#1a2734]';
    textStyle = 'text-white';
  }

  const getMediaIcon = () => {
    switch (media_type) {
      case 'Image':
        return '🖼️';
      case 'Video':
        return '🎥';
      case 'No media':
        return '📝';
      default:
        return '';
    }
  };

  // 获取第一张图片URL
  const getFirstImageUrl = () => {
    if (images_urls && images_urls.length > 0) {
      return images_urls[0];
    }
    if (tweet.media_urls && tweet.media_urls.length > 0) {
      return tweet.media_urls[0];
    }
    return null;
  };

  // 获取头像链接
  const avatarUrl = avatarMap[author_handle] || "https://abs.twimg.com/sticky/default_profile_images/default_profile_normal.png";

  // 计算文本行数
  const calculateTextLines = (text) => {
    const lineHeight = 20; // 假设每行高度为20px
    const containerWidth = 280; // 卡片内容区域宽度
    const fontSize = 14; // 字体大小
    const charsPerLine = Math.floor(containerWidth / (fontSize * 0.6)); // 估算每行字符数
    const lines = Math.ceil(text.length / charsPerLine);
    return lines;
  };

  const textLines = calculateTextLines(text);
  const maxImageHeight = 300; // 图片最大高度
  const minImageHeight = 250; // 图片最小高度改为250px
  const maxTextLines = 5; // 文本最大行数
  const lineHeight = 25; // 每行文本的高度

  // 根据文本行数计算图片高度
  const imageHeight = (media_type === 'Image' || media_type === 'Video') && images_urls && images_urls.length > 0
    ? Math.min(
        maxImageHeight,
        minImageHeight + (maxTextLines - textLines) * lineHeight
      )
    : minImageHeight;

  // 处理图片 URL，移除 name 参数
  const processImageUrl = (url) => {
    if (!url) return url;
    return url.replace(/&name=\d+x\d+/, '');
  };

  return (
    <div 
      className={`rounded-xl shadow-md hover:shadow-lg transition-all duration-300 transform hover:-translate-y-1 hover:scale-[1.02] cursor-pointer ${cardStyle}`}
      onClick={() => window.open(tweet.url, '_blank')}
    >
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2">
            <img
              src={avatarUrl}
              alt={`${author_name}'s avatar`}
              className="w-8 h-8 rounded-full"
            />
            <div>
              <div className="flex items-center space-x-2">
                <p className={`font-semibold text-sm ${textStyle}`}>{author_name}</p>
                <p className="text-gray-400 text-xs">{author_handle}</p>
              </div>
              <p className="text-gray-400 text-xs">{formatDate(date)}</p>
            </div>
          </div>
        </div>

        {media_type === 'No media' ? (
          <div className="text-gray-200 text-sm whitespace-pre-line line-clamp-10 mb-2">
            {text}
          </div>
        ) : (
          <div className="text-gray-200 text-sm whitespace-pre-line line-clamp-5 mb-2">
            {text}
          </div>
        )}

        {media_type === 'Image' && images_urls && images_urls.length > 0 && (
          <div className="relative w-full bg-gray-800 rounded-lg overflow-hidden flex items-center justify-center"
               style={{ height: `${imageHeight}px` }}>
            <img
              src={images_urls[0]}
              alt="Tweet media"
              className="w-full h-full object-cover object-top"
            />
          </div>
        )}

        {media_type === 'Video' && images_urls && images_urls.length > 0 && (
          <div className="relative w-full overflow-hidden rounded-lg"
               style={{ height: `${imageHeight}px` }}>
            <img
              src={processImageUrl(images_urls[0])}
              alt="Video thumbnail"
              className="w-full h-full object-cover object-top"
            />
            <div className="absolute inset-0 flex items-center justify-center bg-black bg-opacity-30 hover:bg-opacity-20 transition-all duration-300">
              <div className="w-16 h-16 rounded-full bg-black bg-opacity-60 flex items-center justify-center">
                <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              </div>
            </div>
          </div>
        )}

        {/* 底部统计信息 */}
        <div className="flex items-center justify-between mt-2 text-gray-500 text-sm">
          <div className="flex items-center space-x-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <span>{formatNumber(num_reply || 0)}</span>
          </div>
          <div className="flex items-center space-x-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            <span>{formatNumber(num_retweet || 0)}</span>
          </div>
          <div className="flex items-center space-x-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
            <span>{formatNumber(num_like || 0)}</span>
          </div>
          <div className="flex items-center space-x-1">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            <span>{formatNumber(num_views || 0)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TweetCard; 