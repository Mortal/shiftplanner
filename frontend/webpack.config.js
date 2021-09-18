const path = require('path');

module.exports = {
  mode: 'development',
  entry: './src/index.tsx',
  output: {
    filename: 'index.js',
    path: path.resolve(__dirname, 'out'),
  },
  module: {
    rules: [
      {
	test: /\.[jt]sx?$/,
	use: {
	  loader: '@sucrase/webpack-loader',
	  options: {
	    transforms: ['jsx', 'typescript']
	  }
	}
      }
    ]
  },
  resolve: {
    extensions: ['.ts', '.js', '.jsx', '.tsx'],
  },
};
