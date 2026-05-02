import 'dotenv/config';
import express from 'express';
import Anthropic from '@anthropic-ai/sdk';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const app = express();
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

app.use(express.json());
app.use(express.static(join(__dirname, 'public')));

const SYSTEM_PROMPT = `あなたはAdobe Illustrator（デスクトップ版）の専門家アシスタントです。
ユーザーがIllustratorで何をしたいかを日本語で説明すると、その操作方法を具体的に教えてください。

必ず以下のJSON形式のみで回答してください（説明文や前置きは不要です）：
{
  "summary": "全体的な説明（1〜2文）",
  "operations": [
    {
      "name": "操作名",
      "shortcut_mac": "Mac用ショートカット（例：Cmd+G）、なければ null",
      "shortcut_win": "Win用ショートカット（例：Ctrl+G）、なければ null",
      "menu_path": "メニューの場所（例：オブジェクト → グループ）、なければ null",
      "panel": "使用するパネル名（例：レイヤーパネル）、なければ null",
      "steps": ["手順1", "手順2", "手順3"],
      "tips": "ヒントや注意点（なければ null）"
    }
  ]
}

関連する操作が複数ある場合はoperationsに複数入れてください。`;

app.post('/api/ask', async (req, res) => {
  const { query } = req.body;
  if (!query || typeof query !== 'string' || query.trim().length === 0) {
    return res.status(400).json({ error: '質問を入力してください' });
  }

  try {
    const message = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      system: SYSTEM_PROMPT,
      messages: [{ role: 'user', content: query.trim() }],
    });

    const text = message.content[0].text;
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) {
      return res.status(500).json({ error: 'AIの回答を解析できませんでした' });
    }

    const result = JSON.parse(jsonMatch[0]);
    res.json(result);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'エラーが発生しました: ' + err.message });
  }
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`Server running at http://localhost:${port}`));
