# Solutions — intended exploit walkthroughs

Spoilers. Keep this away from players. One section per burrow.

---

## burrow1 — Burrow Library (path traversal / LFI, Easy)

**Vuln:** the `/view` route builds a file path from the `file` query parameter
with no containment check (`os.path.join("/app/docs", requested)`), then opens
it. `os.path.join` honors absolute paths and `../` segments escape the docs
directory, so any file readable by the `burrow` user can be read over HTTP.

**Why no shell is needed:** the app runs as the `burrow` user, and the flag at
`/home/burrow/flag.txt` is mode `444` (world-readable). The LFI reads files *as
that user*, so it can read the flag directly — a nice "not every box needs a
reverse shell" lesson.

**Steps**

1. Browse to `http://<host>:8001/`. Note documents are served from
   `/view?file=<name>`.
2. Confirm the parameter is a raw path by escaping the docs directory, e.g.
   read `/etc/passwd`:

   ```bash
   curl 'http://<host>:8001/view?file=../../../../etc/passwd'
   ```

3. Read the flag directly (traversal or an absolute path both work):

   ```bash
   curl 'http://<host>:8001/view?file=../../../../home/burrow/flag.txt'
   # or
   curl 'http://<host>:8001/view?file=/home/burrow/flag.txt'
   ```

4. Submit the `flag{...}` value in the burrow1 box on the scoreboard `/play`
   page.

**What's protected:** the flag is `root:root` `444` inside a `root:root 755`
home dir, so `burrow` can read but not delete or modify it; and `FLAG` is
scrubbed from the process environment on startup, so it can't be recovered from
`/proc/<pid>/environ`.
