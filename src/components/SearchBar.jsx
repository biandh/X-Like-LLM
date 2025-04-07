import { useState } from 'react';
import { FaSearch } from 'react-icons/fa';

function SearchBar({ onSearch }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(input);
  };

  return (
    <form onSubmit={handleSubmit} className="h-full">
      <div className="relative h-full">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="搜索推文或作者..."
          className="w-full h-8 px-4 pl-10 text-gray-700 bg-white border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          className="absolute left-0 top-0 mt-2 ml-3 text-gray-400"
        >
          <FaSearch />
        </button>
      </div>
    </form>
  );
}

export default SearchBar; 