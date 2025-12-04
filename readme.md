PR Summarizer

This project automatically generates pull request titles and summaries using the GitHub API and Google Gemini.

Given a GitHub repository and a number N, the script:
Fetches the latest N merged PRs ,downloads each PR’s diff, and sends the diff to the Gemini model

Generates:
A short PR title , 2–3 sentence summary ad saves all results into results.csv

Usage
Requirements
pip install requests google-generativeai

Run : python main.py

You will be prompted for:
    GitHub repo URL
    GitHub token
    Gemini API key
    Number of PRs to summarize

After running, a file named results.csv will be created containing:
    Original PR title
    Generated PR title
    Original PR summary
    Generated PR summary