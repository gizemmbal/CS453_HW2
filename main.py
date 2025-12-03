import requests
import csv
import google.generativeai as genai
import config  # default keys and settings

MODEL_NAME = "gemini-2.5-flash"


def parse_repo(url: str):
    """Extract (owner, repo) from a GitHub URL."""
    parts = url.strip().split("/")
    return parts[-2], parts[-1]


def get_pr_diff(owner: str, repo: str, pr_number: int, github_token: str) -> str:
    """
    Fetch PR diff text from GitHub.
    Return diff text or empty string if unavailable.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3.diff"
    }

    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.text

    print(f"⚠️ Diff for PR #{pr_number} unavailable.")
    return ""


def ask_gemini(diff_text: str):
    """
    Send diff to Gemini, return generated (title, summary).
    If request fails → return empty strings.
    """
    if not diff_text:
        return "", ""

    # Optional safety crop for very large diffs
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
        print("⚠️ Gemini API error:", e)
        return "", ""


def main():
    repo_url = config.GITHUB_REPO_URL
    github_token = config.GITHUB_TOKEN
    gemini_key = config.GEMINI_API_KEY
    n_prs = config.N_PRS

    if not repo_url or not github_token or not gemini_key:
        print("❌ Missing keys or repo URL in config.py")
        return

    # Setup Gemini API
    genai.configure(api_key=gemini_key)

    owner, repo = parse_repo(repo_url)

    # ------------------------------------------------------------------
    # 2) LAST N MERGED PRs: sayfa sayfa gezerek gerçekten N merged PR topluyoruz
    # ------------------------------------------------------------------
    merged_prs = []
    page = 1
    per_page = 100  # GitHub maksimum

    print(f"Fetching last {n_prs} merged PRs from: https://api.github.com/repos/{owner}/{repo}/pulls")

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

        r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls",
            headers=headers,
            params=params,
        )

        if r.status_code != 200:
            print("❌ GitHub API failed. Status:", r.status_code)
            print(r.text)
            break

        data = r.json()
        if not isinstance(data, list) or not data:
            # Daha fazla PR yok
            break

        for pr in data:
            # Sadece merged PR'ları al
            if pr.get("merged_at"):
                merged_prs.append(pr)
                if len(merged_prs) == n_prs:
                    break

        page += 1

    print(f"Merged PR count collected: {len(merged_prs)}")

    if not merged_prs:
        print("❌ No merged PRs found.")
        return

    rows = []
    for pr in merged_prs:
        number = pr["number"]
        original_title = pr["title"] or ""
        original_summary = pr["body"] or ""

        diff = get_pr_diff(owner, repo, number, github_token)

        print(f"\nProcessing PR #{number}")
        print(f"Diff size: {len(diff)}")

        gen_title, gen_summary = ask_gemini(diff)

        # ------------------------------------------------------------------
        # 3) CSV kolon isimleri ödev PDF'indekiyle birebir aynı
        # ------------------------------------------------------------------
        rows.append({
            "PR #": number,
            "Original PR Title": original_title,
            "Generated PR Title": gen_title,
            "Original PR Summary": original_summary,
            "Generated PR Summary": gen_summary,
        })

    # Write CSV (results.csv)
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

    print(f"\n✅ Saved {len(rows)} rows to results.csv")
    print("Done.")


if __name__ == "__main__":
    main()
