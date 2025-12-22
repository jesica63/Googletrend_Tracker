import express from 'express';
import { fetchAndCleanUrl, fetchMultipleUrls } from '../services/scraperService.js';

const router = express.Router();

/**
 * POST /api/scraper/fetch
 * 抓取單一網址內容
 */
router.post('/fetch', async (req, res, next) => {
  try {
    const { url } = req.body;

    if (!url) {
      return res.status(400).json({
        error: 'Bad Request',
        message: 'url is required'
      });
    }

    // 驗證 URL 格式
    try {
      new URL(url);
    } catch {
      return res.status(400).json({
        error: 'Bad Request',
        message: 'Invalid URL format'
      });
    }

    const result = await fetchAndCleanUrl(url);

    res.json({
      success: true,
      data: result
    });
  } catch (error) {
    next(error);
  }
});

/**
 * POST /api/scraper/fetch-multiple
 * 批次抓取多個網址
 */
router.post('/fetch-multiple', async (req, res, next) => {
  try {
    const { urls, maxUrls = 6 } = req.body;

    if (!Array.isArray(urls)) {
      return res.status(400).json({
        error: 'Bad Request',
        message: 'urls must be an array'
      });
    }

    if (urls.length === 0) {
      return res.status(400).json({
        error: 'Bad Request',
        message: 'urls array is empty'
      });
    }

    // 驗證所有 URL 格式
    for (const url of urls) {
      try {
        new URL(url);
      } catch {
        return res.status(400).json({
          error: 'Bad Request',
          message: `Invalid URL format: ${url}`
        });
      }
    }

    const results = await fetchMultipleUrls(urls, maxUrls);

    if (results.length === 0) {
      return res.status(500).json({
        error: 'Scraping Failed',
        message: 'All URLs failed to fetch. Please check URLs or try again later.'
      });
    }

    res.json({
      success: true,
      data: results,
      meta: {
        total: urls.length,
        succeeded: results.length,
        failed: urls.length - results.length
      }
    });
  } catch (error) {
    next(error);
  }
});

export default router;
