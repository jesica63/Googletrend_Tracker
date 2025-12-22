import { GoogleGenerativeAI, SchemaType } from '@google/generative-ai';

// 初始化 Gemini AI
const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

/**
 * 分析文章並生成內部連結建議
 */
export async function analyzeArticle(articleContent, urlList) {
  if (!process.env.GEMINI_API_KEY) {
    throw new Error('GEMINI_API_KEY is not configured');
  }

  if (!articleContent || articleContent.trim().length === 0) {
    throw new Error('Article content is required');
  }

  // 定義回應的 JSON Schema
  const schema = {
    type: SchemaType.OBJECT,
    properties: {
      revisedArticle: {
        type: SchemaType.STRING,
        description: 'The full article content in Markdown format with the new internal links inserted using [anchor](url) syntax.',
      },
      suggestions: {
        type: SchemaType.ARRAY,
        items: {
          type: SchemaType.OBJECT,
          properties: {
            originalSegment: {
              type: SchemaType.STRING,
              description: 'The original sentence or paragraph before modification.',
            },
            revisedSegment: {
              type: SchemaType.STRING,
              description: 'The contextually optimized sentence containing the new link.',
            },
            anchorText: {
              type: SchemaType.STRING,
              description: 'The exact anchor text used for the link.',
            },
            targetUrl: {
              type: SchemaType.STRING,
              description: 'The URL that was linked to.',
            },
            reason: {
              type: SchemaType.STRING,
              description: 'Explanation in Traditional Chinese.',
            },
          },
          required: ['anchorText', 'targetUrl', 'reason', 'revisedSegment'],
        },
      },
    },
    required: ['revisedArticle', 'suggestions'],
  };

  // 處理 URL 列表
  const processedUrls = urlList.slice(0, 500);
  const urlsText = processedUrls.map((u) => `- ${u.loc || u}`).join('\n');

  // 系統提示詞
  const systemInstruction = `你是一位專業的 SEO 專家與內容策略師。你的任務是分析文章草稿，並為其推薦最適合的內部連結...`;

  const userPrompt = `
    文章內容 (Article Content):
    ${articleContent}

    可用的 Sitemap URLs (Available URLs for Internal Linking):
    ${urlsText}

    請分析這篇文章，並推薦最佳的內部連結位置。
  `;

  try {
    const model = genAI.getGenerativeModel({
      model: 'gemini-2.0-flash-exp',
      generationConfig: {
        responseMimeType: 'application/json',
        responseSchema: schema,
      },
      systemInstruction,
    });

    const result = await model.generateContent(userPrompt);
    const response = result.response;
    const text = response.text();

    if (!text) {
      throw new Error('Empty response from Gemini API');
    }

    return JSON.parse(text);
  } catch (error) {
    console.error('Gemini API error:', error);
    throw new Error(`Failed to analyze article: ${error.message}`);
  }
}

/**
 * 生成策展文章 - Architect 階段
 */
export async function generateArchitecture(topic, outline, scrapedContents) {
  const model = genAI.getGenerativeModel({ model: 'gemini-2.0-flash-exp' });

  const sourcesText = scrapedContents
    .map((s, i) => `[來源 ${i + 1}] ${s.title}\nURL: ${s.url}\n內容:\n${s.content}`)
    .join('\n\n---\n\n');

  const outlineText = outline.map((h, i) => `${i + 1}. ${h}`).join('\n');

  const prompt = `你是一位內容架構師。請根據以下素材，為每個大綱章節撰寫初稿...

大綱:
${outlineText}

參考資料:
${sourcesText}
`;

  const result = await model.generateContent(prompt);
  return result.response.text();
}

/**
 * 生成策展文章 - Editor 階段
 */
export async function generateFinalArticle(topic, intro, architectDrafts, scrapedContents) {
  const model = genAI.getGenerativeModel({ model: 'gemini-2.0-flash-exp' });

  const draftsText = architectDrafts
    .map((d) => `## ${d.sectionTitle}\n${d.content}`)
    .join('\n\n');

  const sourcesTable = scrapedContents
    .map((s, i) => `${i + 1}. [${s.title}](${s.url})`)
    .join('\n');

  const companyStyleGuide = `
- 語氣：專業但親切，避免過度學術或冷硬的表達
- 段落長度：每段 250-550 字為佳
- 禁用詞：避免「讓我們繼續看下去」、「廢話不多說」等口語化銜接詞
`;

  const prompt = `你是總編輯。請將以下初稿潤飾成一篇完整的 HTML 文章...

主題: ${topic}
開場白: ${intro}

初稿內容:
${draftsText}

風格指南:
${companyStyleGuide}

延伸閱讀來源:
${sourcesTable}
`;

  const result = await model.generateContent(prompt);
  let html = result.response.text();

  // 清理 HTML
  html = html.replace(/```html/g, '').replace(/```/g, '').trim();

  return html;
}
