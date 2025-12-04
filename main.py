import requests
import csv
import google.generativeai as genai

MODEL_NAME = "gemini-2.5-flash"


def parse_repo(url: str):
    parts = url.strip().rstrip("/").split("/")
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repo URL.")
    return parts[-2], parts[-1]


def get_pr_diff(owner: str, repo: str, pr_number: int, github_token: str) -> str:
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.text
    print(f"PR #{pr_number} diff could not be retrieved. Status: {r.status_code}")
    return ""


def ask_gemini(diff_text: str):
    if not diff_text:
        return "", ""

    if len(diff_text) > 8000:
        diff_text = diff_text[:8000]

    prompt = f"""
You are a code reviewer assistant.
Given the following GitHub pull request diff, produce:

1) A short, meaningful, professional title for the PR.
2) A concise summary explaining the change in 2–3 sentences.

Output EXACTLY in this format:

TITLE: <generated title>
SUMMARY: <generated summary>
---

DIFF:
{diff_text}
"""

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        if not response:
            return "", ""

        text = (getattr(response, "text", "") or "").strip()

        title, summary = "", ""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()

        return title, summary

    except Exception as e:
        print("Gemini API error:", e)
        return "", ""


def main():
    repo_url = input("GitHub Repo URL: ").strip()
    github_token = input("GitHub Token: ").strip()
    gemini_key = input("Gemini API Key: ").strip()
    n_prs_str = input("Number of PRs to summarize: ").strip()

    try:
        n_prs = int(n_prs_str)
        if n_prs <= 0:
            print("PR count must be a positive integer.")
            return
    except ValueError:
        print("Invalid PR count.")
        return

    if not repo_url or not github_token or not gemini_key:
        print("Missing required inputs.")
        return

    genai.configure(api_key=gemini_key)

    try:
        owner, repo = parse_repo(repo_url)
    except ValueError as e:
        print(e)
        return

    merged_prs = []
    page = 1
    per_page = 100
    base_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"

    print(f"Fetching last {n_prs} merged PRs from {base_url}...")

    while len(merged_prs) < n_prs:
        params = {
            "state": "closed",
            "sort": "updated",
            "direction": "desc",
            "per_page": per_page,
            "page": page,
        }
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github+json",
        }

        r = requests.get(base_url, headers=headers, params=params)
        if r.status_code != 200:
            print("GitHub API error:", r.status_code)
            print(r.text)
            return

        data = r.json()
        if not isinstance(data, list) or not data:
            break

        for pr in data:
            if pr.get("merged_at"):
                merged_prs.append(pr)
                if len(merged_prs) == n_prs:
                    break

        page += 1

    if not merged_prs:
        print("No merged PRs found.")
        return

    if len(merged_prs) < n_prs:
        print(f"Only {len(merged_prs)} merged PRs found.")
    else:
        print(f"{len(merged_prs)} merged PRs collected.")

    print("Generating titles and summaries...")

    rows = []

    for pr in merged_prs:
        number = pr["number"]
        original_title = pr.get("title") or ""
        original_summary = pr.get("body") or ""

        diff = get_pr_diff(owner, repo, number, github_token)

        print(f"\nProcessing PR #{number}")
        print(f"Diff size: {len(diff)} characters")

        gen_title, gen_summary = ask_gemini(diff)

        rows.append({
            "PR #": number,
            "Original PR Title": original_title,
            "Generated PR Title": gen_title,
            "Original PR Summary": original_summary,
            "Generated PR Summary": gen_summary,
        })

    fields = [
        "PR #",
        "Original PR Title",
        "Generated PR Title",
        "Original PR Summary",
        "Generated PR Summary",
    ]

    with open("results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"\nSaved {len(rows)} rows to results.csv")


if __name__ == "__main__":
    main()
