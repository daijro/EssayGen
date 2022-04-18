# EssayGen

<strong>(Educational purposes only)</strong>

ShortlyAI is an advanced essay generating tool that uses the GPT-3 AI. Its demo only allows you to run it up to 4 times before it locks your access and requries you to pay $79/month. This bot will register new demo accounts, and allow you to continue generating your essay.

<hr width=50>

## Installation

**Download Windows binaries [here](https://github.com/daijro/essaygen/releases)**

To run from source code, install the requirements:

```
pip3 install -r requirements.txt
```
(Tested on [Python 3.8.9](https://www.python.org/downloads/release/python-389/))


<hr width=50>

## Usage

- Select an essay type (article or story)
- Enter an essay title
- Enter the starting content of your essay
- (optional) Enter a brief overview of your essay
- Choose the length of each generated segment using the slider
- Move your text cursor to where you want your AI to write
- Click "Generate" to run *(or Ctrl+Enter)*


#### Effectively using GPT-3

To find more tips on how to effectly make use of GPT-3, you can visit the [ShortlyAI docs](https://help.shortlyai.com/), or go to [this video tutorial](https://www.youtube.com/watch?v=5bnN6PjhDUE).


#### Supported Features

- **Article writing** (non-fiction mode)
- **Story writing** (creative fiction mode)
- **Title** - Specify a essay title to influence the AI's output
- **Article brief/story outline** - Specifiy an article outline/summary or a story background for the AI
- **[Slash commands](https://help.shortlyai.com/getting-started/slash-commands)**
    
| Command                | Description                                                                       	| Hotkey     	|  Char Limit 	|
|------------------------|-----------------------------------------------------------------------------------	|------------	| ------------	|
| *`/instruct [text]`* 	 | Give instructions on what the AI should write next. [More details](https://help.shortlyai.com/getting-started/slash-commands#instruct)	| Ctrl+Enter 	|  500        	|
| *`/rewrite [text]`*    | Rewrites text in a unique way                                                     	| Ctrl+P     	|  160        	|
| *`/shorten [text]`*    | Shortens text to make it more concise                                             	| Ctrl+[     	|  200        	|
| *`/expand [text]`*     | Extends and develops text                                                         	| Ctrl+]     	|  120        	|
- **Writing stats**: Displays character count, char count (without spaces), and word count of either the selected text or entire text *(Ctrl+Shift+C)*

- **[`///` content seperators](https://help.shortlyai.com/getting-started/understanding-context#using)** - Isolates content to prevent earlier sections of your writing from influencing the AI's output. For example, if the content above is a list, but you no longer wish to to write in a list format, this can be helpful.




<hr width=50>

## Screenshot

![image](https://user-images.githubusercontent.com/72637910/163756731-0000736a-c748-4b57-810f-30f9933aea6c.png)


<hr width=50>

## Disclaimer

This bot is meant to demonstrate how QWebEngine & requests can be used in webscraping and is for EDUCATIONAL PURPOSES ONLY! Please consider supporting the developers.
