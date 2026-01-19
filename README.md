# rdpscreenshotter
A Windows-only RDP Screenshotter with Telegram integration. Based on Python, made by Google Gemini and OpenAI ChatGPT.
* Note: This tool only for educational and security purpose, I will not responsible for anything you have done. 

# How to use?
* Step 0: Install these pip modules (if you decide to use main.py): requests, pywin32, pillow, numpy, certifi
* Step 1: Create a file named "good.txt". Inside the file, set each line corresponding each RDP you want to screenshot as this format: "{1}:{2}@{3}\\{4};{5}"
  Where:
	- {1}: IP Address of targetted RDP
	- {2}: Open port number for RDP
	- {3}: Domain or Machine name of targetted RDP
	- {4}: Username of targetted RDP
	- {5}: Password of targetted RDP
* Step 2: Download wfreerdp executable from https://ci.freerdp.com/job/freerdp-nightly-windows/ and place both wfreerdp and the pre-compiled file (or main.py from the source code) to the same folder that contains the "good.txt" file.
* Step 3: Launch the pre-compiled file (or main.py), set your desired settings.
* Step 4: Profits?

# Report a bug or FAQs?
uhhhhh no, asks Gemini or ChatGPT to help u instead lmao
