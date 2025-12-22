import express from 'express';
import { analyzeArticle, generateArchitecture, generateFinalArticle } from '../services/geminiService.js';

const router = express.Router();

/**
 * POST /api/gemini/analyze
 * 分析文章並生成內部連結建議
 */
router.post('/analyze', async (req, res, next) => {
  try {
    const { articleContent, urlList } = req.body;

    if (!articleContent) {
      return res.status(400).json({
        error: 'Bad Request',
        message: 'articleContent is required'
      });
    }

    if (!Array.isArray(urlList)) {
      return res.status(400).json({
        error: 'Bad Request',
        message: 'urlList must be an array'
      });
    }

    console.log(`[Gemini] Analyzing article (${articleContent.length} chars) with ${urlList.length} URLs`);

    const result = await analyzeArticle(articleContent, urlList);

    res.json({
      success: true,
      data: result
    });
  } catch (error) {
    next(error);
  }
});

/**
 * POST /api/gemini/architect
 * 生成文章架構初稿
 */
router.post('/architect', async (req, res, next) => {
  try {
    const { topic, outline, scrapedContents } = req.body;

    console.log(`[Gemini] Generating architecture for: ${topic}`);

    const result = await generateArchitecture(topic, outline, scrapedContents);

    res.json({
      success: true,
      data: result
    });
  } catch (error) {
    next(error);
  }
});

/**
 * POST /api/gemini/editor
 * 生成最終文章
 */
router.post('/editor', async (req, res, next) => {
  try {
    const { topic, intro, architectDrafts, scrapedContents } = req.body;

    console.log(`[Gemini] Generating final article for: ${topic}`);

    const result = await generateFinalArticle(topic, intro, architectDrafts, scrapedContents);

    res.json({
      success: true,
      data: result
    });
  } catch (error) {
    next(error);
  }
});

export default router;
