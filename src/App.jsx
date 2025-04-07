import { useState, useEffect } from 'react';
import TweetCard from './components/TweetCard';
import SearchBar from './components/SearchBar';
import FilterBar from './components/FilterBar';
import React from 'react';

function App() {
  const [tweets, setTweets] = useState([]);
  const [filteredTweets, setFilteredTweets] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('likes');
  const [sortOrder, setSortOrder] = useState('desc');
  const [minLikes, setMinLikes] = useState('');
  const [minRetweets, setMinRetweets] = useState('');
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [mediaType, setMediaType] = useState('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(50);

  useEffect(() => {
    // 读取 JSONL 文件
    fetch('/data/x.jsonl')
      .then(response => response.text())
      .then(text => {
        const tweets = text
          .split('\n')
          .filter(line => line.trim())
          .map(line => JSON.parse(line))
          .sort((a, b) => new Date(b.date) - new Date(a.date)); // 初始加载时就按日期排序
        setTweets(tweets);
        setFilteredTweets(tweets);
      })
      .catch(error => console.error('Error loading tweets:', error));
  }, []);

  useEffect(() => {
    let filtered = [...tweets];

    // 搜索过滤
    if (searchTerm) {
      filtered = filtered.filter(tweet => 
        tweet.text.toLowerCase().includes(searchTerm.toLowerCase()) ||
        tweet.author_name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // 最小点赞数过滤
    if (minLikes) {
      filtered = filtered.filter(tweet => tweet.num_like >= parseInt(minLikes));
    }

    // 最小转发数过滤
    if (minRetweets) {
      filtered = filtered.filter(tweet => tweet.num_retweet >= parseInt(minRetweets));
    }

    // 日期范围过滤
    if (dateRange.start && dateRange.end) {
      filtered = filtered.filter(tweet => {
        const tweetDate = new Date(tweet.date);
        const startDate = new Date(dateRange.start);
        const endDate = new Date(dateRange.end);
        return tweetDate >= startDate && tweetDate <= endDate;
      });
    }

    // 媒体类型过滤
    if (mediaType !== 'all') {
      filtered = filtered.filter(tweet => tweet.media_type === mediaType);
    }

    // 排序
    filtered.sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'date') {
        comparison = new Date(b.date) - new Date(a.date);
      } else if (sortBy === 'likes') {
        comparison = (b.num_like || 0) - (a.num_like || 0);
      } else if (sortBy === 'retweets') {
        comparison = (b.num_retweet || 0) - (a.num_retweet || 0);
      }
      return sortOrder === 'asc' ? -comparison : comparison;
    });

    setFilteredTweets(filtered);
  }, [searchTerm, tweets, sortBy, sortOrder, minLikes, minRetweets, dateRange, mediaType]);

  const handleSearch = (term) => {
    setSearchTerm(term);
  };

  const handleFilterChange = (type, value) => {
    switch (type) {
      case 'sortBy':
        setSortBy(value);
        break;
      case 'sortOrder':
        setSortOrder(value);
        break;
      case 'minLikes':
        setMinLikes(value);
        break;
      case 'minRetweets':
        setMinRetweets(value);
        break;
      case 'dateRange':
        setDateRange(value);
        break;
      case 'mediaType':
        setMediaType(value);
        break;
      case 'itemsPerPage':
        setItemsPerPage(value);
        setCurrentPage(1); // 重置到第一页
        break;
      default:
        break;
    }
  };

  const totalPages = Math.ceil(filteredTweets.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentTweets = filteredTweets.slice(startIndex, endIndex);

  const handlePageChange = (page) => {
    setCurrentPage(page);
    window.scrollTo(0, 0);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">X-Like LLM</h1>
        
        <div className="flex justify-between items-center mb-4">
          <div className="w-5/6">
            <FilterBar 
              onFilterChange={handleFilterChange} 
              mediaType={mediaType}
              itemsPerPage={itemsPerPage}
            />
          </div>
          <div className="w-1/6">
            <SearchBar onSearch={handleSearch} />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {currentTweets.map((tweet) => (
            <TweetCard key={tweet.id} tweet={tweet} />
          ))}
        </div>

        {totalPages > 1 && (
          <div className="flex justify-center mt-8 space-x-2">
            <button
              onClick={() => handlePageChange(1)}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded-md bg-white border text-sm disabled:opacity-50"
            >
              首页
            </button>
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded-md bg-white border text-sm disabled:opacity-50"
            >
              上一页
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter(page => 
                page === 1 || 
                page === totalPages || 
                (page >= currentPage - 2 && page <= currentPage + 2)
              )
              .map((page, index, array) => (
                <React.Fragment key={page}>
                  {index > 0 && array[index - 1] !== page - 1 && (
                    <span key={`ellipsis-${page}`} className="px-3 py-1">...</span>
                  )}
                  <button
                    onClick={() => handlePageChange(page)}
                    className={`px-3 py-1 rounded-md text-sm ${
                      currentPage === page
                        ? 'bg-blue-500 text-white'
                        : 'bg-white border'
                    }`}
                  >
                    {page}
                  </button>
                </React.Fragment>
              ))}
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="px-3 py-1 rounded-md bg-white border text-sm disabled:opacity-50"
            >
              下一页
            </button>
            <button
              onClick={() => handlePageChange(totalPages)}
              disabled={currentPage === totalPages}
              className="px-3 py-1 rounded-md bg-white border text-sm disabled:opacity-50"
            >
              末页
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default App; 