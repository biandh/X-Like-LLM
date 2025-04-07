import { FaHeart, FaRetweet, FaComment, FaExternalLinkAlt } from 'react-icons/fa';

function TweetCard({ tweet }) {
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

  const getCardStyle = () => {
    switch (tweet.media_type) {
      case 'Image':
        return 'bg-gradient-to-br from-amber-50 to-amber-100/50 border-amber-200/50';
      case 'Video':
        return 'bg-gradient-to-br from-emerald-50 to-emerald-100/50 border-emerald-200/50';
      case 'No media':
        return 'bg-gradient-to-br from-slate-50 to-slate-100/50 border-slate-200/50';
      default:
        return 'bg-gradient-to-br from-slate-50 to-slate-100/50 border-slate-200/50';
    }
  };

  const getMediaIcon = () => {
    switch (tweet.media_type) {
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
    if (tweet.images_urls && tweet.images_urls.length > 0) {
      return tweet.images_urls[0];
    }
    if (tweet.media_urls && tweet.media_urls.length > 0) {
      return tweet.media_urls[0];
    }
    return null;
  };

  return (
    <div 
      className={`rounded-xl shadow-md border p-4 hover:shadow-lg transition-all duration-300 transform hover:-translate-y-1 backdrop-blur-sm ${getCardStyle()}`}
      onClick={() => window.open(tweet.url, '_blank')}
    >
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center space-x-2">
          <span className="text-lg">{getMediaIcon()}</span>
          <span className="font-medium text-gray-800">{tweet.author_name}</span>
        </div>
        <span className="text-[13px] text-gray-500">{formatDate(tweet.date)}</span>
      </div>
      
      <p className="text-sm text-gray-700 line-clamp-5">{tweet.text}</p>
      
      {getFirstImageUrl() && (
        <div className="mt-3">
          <div className="relative w-full max-h-[300px] overflow-hidden rounded-lg">
            <img
              src={getFirstImageUrl()}
              alt="Tweet media"
              className="w-full h-auto object-cover"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          </div>
        </div>
      )}
      
      <div className="flex items-center justify-between text-gray-500 text-sm mt-3">
        <div className="flex items-center space-x-4">
          <span className="flex items-center">
            <FaHeart className="mr-1" />
            {tweet.num_like || 0}
          </span>
          <span className="flex items-center">
            <FaRetweet className="mr-1" />
            {tweet.num_retweet || 0}
          </span>
          <span className="flex items-center">
            <FaComment className="mr-1" />
            {tweet.num_reply || 0}
          </span>
        </div>
        <FaExternalLinkAlt className="text-gray-400" />
      </div>
    </div>
  );
}

export default TweetCard; 