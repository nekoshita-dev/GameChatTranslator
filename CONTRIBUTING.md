# 開発に参加するには

GameChat Translator への協力ありがとうございます。特に歓迎しているのは次の3つです。

1. **新しいゲームへの対応**（プロファイルの追加）
2. **辞書の追加・修正**（スラングやゲーム用語）
3. **動作報告**（このゲームで動いた／動かなかった）

プログラムを書かなくても、1と2はファイルを編集するだけでできます。

## 新しいゲームに対応する

### 1. プロファイルを作る

`profiles/generic.toml` をコピーして、`profiles/<ゲームID>.toml` を作ります。ゲームIDは半角英小文字（例：`overwatch2`、`cs2`）にしてください。

```toml
name = "ゲームの正式名"
notes = "起動時に表示する注意（無ければ空欄）"

[chat]
open_key = "enter"        # チャット欄を開くキー
alt_open_key = ""         # 2つ目のチャット（全体チャットなど）。無ければ ""
send_key = "enter"        # 送信キー
open_delay = 0.15         # チャット欄が開くまでの待ち時間（秒）
key_delay = 0.012         # 1文字ごとの間隔（秒）
max_chars = 120           # 1回に送れる最大文字数（ゲームの上限に合わせる）
ime_off = true            # 入力中だけ日本語入力をオフにする

[dictionary]
slang = ["<ゲームID>.slang.csv"]
speech = ["<ゲームID>.speech.csv"]
```

キーの書き方：`"enter"`、`"y"`、`"shift+enter"`、`"f1"`、`"/"` など。使える名前は `gamechat/winkeys.py` の `_NAMED_VK` を見てください。

### 2. 辞書を作る（任意）

- `profiles/<ゲームID>.slang.csv`（`term,expand,ja`）：相手のチャットに出てくるそのゲーム特有の略語
- `profiles/<ゲームID>.speech.csv`（`ja,en`）：自分が話すそのゲームの用語（武器名、場所、役割など）

書き方は README の「辞書で精度を上げる」を参照してください。全ゲーム共通の語は `dict/` のファイルに追加してください。

### 3. 試す

```
run.bat --game <ゲームID>
```

`open_delay` と `key_delay` は、ゲームによってちょうどいい値が違います。文字が欠けるなら増やしてください。

### 4. 送る

Pull Request の説明に次のことを書いてください。

- ゲーム名と、確認した日（ゲームのアップデートで変わることがあるため）
- チャットキーが初期設定かどうか
- 送信・読み取り・表示のそれぞれが動いたか

## 辞書を直す・増やす

- 1語だけで意味が通るスラングは `ja` に訳を入れると、翻訳エンジンを通さず確実に表示できます
- 漢字1文字の語（「冲」「上」など）は、`expand` を空欄にしてください。文の中で置き換えると別の単語を壊します
- 英語の短い語（「u」「w」など）も、別の意味に取られやすいものは `expand` を空欄にしてください
- ファイルは **UTF-8** で保存してください（Excel なら「CSV UTF-8」）

## プログラムを直す

```
setup.bat
venv\Scripts\activate
python -m pytest tests
```

| ファイル | 役割 |
|---|---|
| `gamechat/app.py` | 全体の流れ、キーの見張り |
| `gamechat/config.py` | 設定・プロファイルの読み込み |
| `gamechat/voice.py` | 録音、音声認識、英訳 |
| `gamechat/chatreader.py` | 画面の読み取り → 翻訳 |
| `gamechat/textproc.py` | 行の解析、重複チェック、辞書 |
| `gamechat/winkeys.py` | Windows のキー入力・判定 |
| `gamechat/overlay.py` | 翻訳の表示、範囲選択 |
| `gamechat/translate.py` | Google / DeepL 翻訳 |
| `gamechat/ocr.py` | 文字の読み取り |
| `gamechat/logutil.py` | ログファイル |

設定の初期値を変えるときは、`gamechat/config.py` の `DEFAULT_SETTINGS` と `settings.default.toml` の両方を直してください。変更したら `CHANGELOG.md` にも書いてください。

## 守ってほしいこと

- ゲームのメモリやファイルを読み書きする機能、ゲームを有利にする機能（チート）は追加しません
- 他の人への嫌がらせに使える機能（連投など）は追加しません
