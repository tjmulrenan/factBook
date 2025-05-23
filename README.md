# 📚 Factbook Project

A Python-powered pipeline for generating fun, illustrated children's factbooks—one magical day at a time!

## 📂 Project Structure

Root Directory:  
`C:\Users\tmulrenan\Desktop\Factbook Project`

Folders:
- `facts/` — Raw and processed fact JSON files.
- `books/` — Final generated PDF books.

## 🚀 Workflow Overview

This project creates fun, educational PDF books for kids aged 8–12 using historical facts from public APIs, AI enhancements, and image generation.

---

## 🛠 Step-by-Step Instructions

### 1. 🔍 Generate Raw Facts
Navigate to the root directory in the command line:

```bash
cd "C:\Users\tmulrenan\Desktop\Factbook Project"
python .\generateFacts.py
```

You'll be prompted to enter:
- A **month** (e.g., `January`)
- A **day** (e.g., `14`)

This script collects:
- Major historical events from Wikipedia
- Curiosities and trivia from Numbers API

✅ **Output**:  
A raw JSON file is saved to:

```
facts\[Month]_[Day].json
```

Example:
```
facts\March_29.json
```

---

### 2. ✨ Enhance and Categorize Facts

Now process and clean the data with AI assistance:

```bash
cd facts
python.exe .\factEnhancer.py
```

This:
- De-duplicates facts
- Rewrites them using **Claude 3 Sonnet (20250219)** to make them fun, story-like, and kid-friendly
- Assigns each fact to one of ~20 curated categories like `Space Exploration`, `Famous Portraits`, or `Sporting Achievements`

✅ **Output**:  
Enhanced JSON saved to:

```
facts\sorted\[Month]_[Day]_AI_rewritten_sorted.json
```

Sample format:

```json
{
  "title": "The Space Explorer with a Special Birthday",
  "story": "On this very day in 1950, a baby named George Nelson was born who would one day float among the stars! ...",
  "category": "Space Exploration",
  "id": 1
}
```

---

### 3. 📖 Generate the Factbook PDF

From the project root:

```bash
python .\generateBook.py
```

This compiles the enhanced facts into a beautifully illustrated, category-organized PDF children's book.

✅ **Output**:  
Saved to:

```
books\[Month]_[Day]_AI_rewritten_sorted.pdf
```

If a file with the same name exists, it will automatically increment:
```
March_29_AI_rewritten_sorted_1.pdf
```

---

## 📌 Features

- ⚡ Fast API-powered fact retrieval
- 🧠 Claude AI integration for natural, engaging storytelling
- 🧒 Kid-friendly formatting, tone, and vocabulary
- 🖼️ Minimalist illustrations and emojis by category
- 🕹️ Random jokes and trivia footers for extra fun

---

## 💡 Suggested Improvements

Here are a few ideas for making this even more powerful:

| Feature | Description |
|--------|-------------|
| ✅ CLI Argument Support | Let users pass the date via CLI args to skip manual input (`--month March --day 29`) |
| 🧪 Unit Tests | Add basic test scripts to ensure each step outputs expected formats |
| 📤 Export Options | Add EPUB or HTML output alongside PDF |
| 💬 AI Retry Logic | Automatically handle and retry malformed Claude responses |
| 🌐 GUI Wrapper | Simple Tkinter or web-based interface for user-friendly book generation |
| 📸 Custom Image Folder | Let users optionally provide or override images per category |

---

## 👨‍💻 Author

Created by **TJ Mulrenan** (aka Timothy John Mulrenan) — inspired by a love for facts, storytelling, and sparking curiosity in young minds!
