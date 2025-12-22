/**
 * 統一錯誤處理中間件
 */
export function errorHandler(err, req, res, next) {
  console.error('Error:', err);

  // 默認錯誤狀態碼
  const statusCode = err.statusCode || 500;

  // 錯誤響應
  res.status(statusCode).json({
    error: err.name || 'Internal Server Error',
    message: err.message || 'Something went wrong',
    ...(process.env.NODE_ENV === 'development' && {
      stack: err.stack
    })
  });
}
