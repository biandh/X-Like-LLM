import { FaFilter } from 'react-icons/fa';

const FilterBar = ({ onFilterChange, mediaType, itemsPerPage, author, topAuthors, onMediaTypeChange }) => {
  return (
    <div className="h-full">
      <div className="flex items-center h-full space-x-3">
        <div className="flex items-center space-x-1.5">
          <FaFilter className="text-gray-400" />
          <label className="text-sm text-gray-600">排序：</label>
          <select
            onChange={(e) => onFilterChange('sortBy', e.target.value)}
            className="h-7 px-2 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="date">最新日期</option>
            <option value="likes">喜欢次数</option>
            <option value="retweets">转发次数</option>
            <option value="replies">回复次数</option>
            <option value="views">查看次数</option>
          </select>
          <select
            onChange={(e) => onFilterChange('sortOrder', e.target.value)}
            className="h-7 px-2 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="desc">降序</option>
            <option value="asc">升序</option>
          </select>
        </div>
        <div className="flex items-center space-x-1.5">
          <label className="text-sm text-gray-600">最小点赞：</label>
          <input
            type="number"
            onChange={(e) => onFilterChange('minLikes', e.target.value)}
            className="h-7 w-16 px-2 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="0"
          />
        </div>
        <div className="flex items-center space-x-1.5">
          <label className="text-sm text-gray-600">最小转发：</label>
          <input
            type="number"
            onChange={(e) => onFilterChange('minRetweets', e.target.value)}
            className="h-7 w-16 px-2 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="0"
          />
        </div>
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600">媒体类型：</label>
          <select
            value={mediaType}
            onChange={(e) => onMediaTypeChange(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="all">全部</option>
            <option value="text">文本</option>
            <option value="image">图文</option>
            <option value="video">视频</option>
          </select>
        </div>

        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600">作者：</label>
          <select
            value={author}
            onChange={(e) => onFilterChange('author', e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value="all">全部作者</option>
            {topAuthors.map((author) => (
              <option key={author.handle} value={author.handle}>
                {author.name}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600">每页数量：</label>
          <select
            value={itemsPerPage}
            onChange={(e) => onFilterChange('itemsPerPage', parseInt(e.target.value))}
            className="h-7 px-2 border rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="50">50</option>
            <option value="100">100</option>
            <option value="200">200</option>
            <option value="500">500</option>
          </select>
        </div>
      </div>
    </div>
  );
}

export default FilterBar; 