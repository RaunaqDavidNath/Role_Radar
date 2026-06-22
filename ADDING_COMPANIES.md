# Adding a new company to track

Every company's careers page is hosted on one of a handful of platforms.
You can tell which one just by looking at the URL, or where it redirects
to when you click "View open roles" on their site.

## Step 1: Find the platform from the URL pattern

| If the careers URL looks like... | Platform | board_id is... |
|---|---|---|
| `jobs.ashbyhq.com/CompanyName` | ashby | `CompanyName` |
| `boards.greenhouse.io/CompanyName` | greenhouse | `CompanyName` |
| `jobs.lever.co/CompanyName` | lever | `CompanyName` |

The `board_id` is almost always just the company-name segment at the end
of the URL, lowercase, no spaces.

**Example:** if a company's careers page is `jobs.lever.co/notion`, then:
```python
{"name": "Notion", "platform": "lever", "board_id": "notion"}
```

## Step 2: Don't know the URL? Search for it

If a company's main site just says "Careers" with no obvious link, search
for `"<company name>" careers jobs.lever.co OR boards.greenhouse.io OR jobs.ashbyhq.com`
-- one of those three usually turns up if they use a common platform.

## Step 3: What if it's none of the three?

Plenty of larger companies use Workday, SmartRecruiters, or a fully custom
in-house careers page instead. Those aren't supported yet. Adding one means
writing a single new adapter function, following the same pattern as the
existing three, registered in `PLATFORM_FETCHERS` — provided the platform
exposes a free, public, keyless API.

## Step 4: Add it to the script

Open `job_alert.py`, find the `COMPANIES` list, and add a line:
```python
COMPANIES = [
    {"name": "Atlan", "platform": "ashby", "board_id": "atlan"},
    {"name": "Notion", "platform": "lever", "board_id": "notion"},   # new
]
```

That's it -- no other code changes needed. The next time the script runs,
it'll start checking that company too, using the same AI filter and the
same dual notification (Mac + Android).
