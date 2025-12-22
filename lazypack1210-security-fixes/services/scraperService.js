import fetch from 'node-fetch';
import * as cheerio from 'cheerio';

/**
 * 抓取並清理網頁內容
 * @param {string} url - 目標網址
 * @returns {Promise<Object>} 包含 id, url, title, content 的物件
 */
export async function fetchAndCleanUrl(url, scraperIndex = 1) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000); // 15秒超時

  try {
    console.log(`[Scraper] Fetching: ${url}`);

    // 直接抓取，不使用第三方代理
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const html = await response.text();
    clearTimeout(timeoutId);

    // 使用 Cheerio 解析 HTML
    const $ = cheerio.load(html);

    // 移除不需要的元素
    $(
      'script, style, nav, header, footer, aside, iframe, noscript, [role="navigation"], [role="banner"], [role="complementary"]'
    ).remove();

    // 提取標題
    let title = $('title').text().trim();
    if (!title) {
      title = $('h1').first().text().trim();
    }
    if (!title) {
      title = url;
    }

    // 提取主要內容
    let content = '';

    // 嘗試找到主要內容區域
    const mainSelectors = [
      'article',
      '[role="main"]',
      'main',
      '.content',
      '.article-content',
      '#content',
      '.post-content',
      '.entry-content',
    ];

    let $main = null;
    for (const selector of mainSelectors) {
      $main = $(selector).first();
      if ($main.length > 0) {
        break;
      }
    }

    // 如果找到主要內容區域，使用它；否則使用 body
    if ($main && $main.length > 0) {
      content = $main.text();
    } else {
      content = $('body').text();
    }

    // 清理內容
    content = content
      .replace(/\s+/g, ' ') // 移除多餘空白
      .replace(/\n+/g, '\n') // 移除多餘換行
      .trim()
      .slice(0, 20000); // 限制 20,000 字符

    if (content.length < 100) {
      throw new Error('Content too short after cleaning (< 100 characters)');
    }

    console.log(`[Scraper] Success: ${url} (${content.length} chars)`);

    return {
      id: scraperIndex,
      url,
      title,
      content,
    };
  } catch (error) {
    clearTimeout(timeoutId);

    if (error.name === 'AbortError') {
      throw new Error(`Request timeout for ${url}`);
    }

    console.error(`[Scraper] Error fetching ${url}:`, error.message);
    throw new Error(`Failed to fetch ${url}: ${error.message}`);
  }
}

/**
 * 批次抓取多個網址
 * @param {string[]} urls - 網址列表
 * @param {number} maxUrls - 最多抓取幾個網址
 * @returns {Promise<Object[]>} 抓取成功的內容列表
 */
export async function fetchMultipleUrls(urls, maxUrls = 6) {
  const limitedUrls = urls.slice(0, maxUrls);

  console.log(`[Scraper] Starting batch fetch for ${limitedUrls.length} URLs`);

  const promises = limitedUrls.map((url, index) =>
    fetchAndCleanUrl(url, index + 1)
      .then((result) => ({ status: 'fulfilled', value: result }))
      .catch((error) => ({ status: 'rejected', reason: error.message }))
  );

  const results = await Promise.all(promises);

  const successful = results
    .filter((r) => r.status === 'fulfilled')
    .map((r) => r.value);

  const failed = results.filter((r) => r.status === 'rejected');

  console.log(`[Scraper] Batch complete: ${successful.length} succeeded, ${failed.length} failed`);

  if (failed.length > 0) {
    console.log('[Scraper] Failed URLs:', failed.map((f) => f.reason));
  }

  return successful;
}
