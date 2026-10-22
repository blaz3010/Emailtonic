import { useCallback, useEffect, useRef, useState } from "react";

/* ------------------------------------------------------------------ */
/*  Config + API                                                       */
/* ------------------------------------------------------------------ */

const API =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
  "http://localhost:8000";

// The access token lives in memory only and is sent as a Bearer header.
// The refresh token stays in an HttpOnly cookie managed by the backend.
let accessToken = null;
function setAccessToken(token) {
  accessToken = token;
}

function errorText(data, fallback) {
  const d = data?.detail;
  if (!d) return fallback;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join(". ");
  return fallback;
}

async function api(path, { method = "GET", json, form, retry = true } = {}) {
  const init = { method, credentials: "include", headers: {} };
  if (accessToken) init.headers.Authorization = `Bearer ${accessToken}`;
  if (json) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(json);
  }
  if (form) init.body = form;

  let res;
  try {
    res = await fetch(API + path, init);
  } catch {
    throw new Error("Can't reach the server. Check that the backend is running.");
  }

  if (res.status === 401 && retry && !path.startsWith("/user/login")) {
    const refreshed = await refreshSession();
    if (refreshed) return api(path, { method, json, form, retry: false });
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const err = new Error(errorText(data, `Request failed (${res.status})`));
    err.status = res.status;
    throw err;
  }
  return data;
}

async function refreshSession() {
  try {
    const res = await fetch(API + "/user/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) return false;
    const data = await res.json();
    setAccessToken(data.access_token);
    return true;
  } catch {
    return false;
  }
}

/* ------------------------------------------------------------------ */
/*  Styles                                                             */
/* ------------------------------------------------------------------ */

const css = `
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,600;12..96,700&family=Figtree:wght@400;500;600&display=swap');

:root {
  --paper: #f8f7f4;
  --surface: #fdfcfb;
  --line: #e4e1da;
  --line-strong: #cfcbc2;
  --ink: #23202b;
  --ink-soft: #6a6575;
  --purple: #5b34c9;
  --purple-deep: #46279f;
  --purple-wash: #ede8fa;
  --danger: #b3261e;
  --ok: #2f6b4f;
  --head: 'Bricolage Grotesque', 'Segoe UI', sans-serif;
  --body: 'Figtree', 'Segoe UI', sans-serif;
}

* { box-sizing: border-box; }
/* The app is light-only. Pin it so the Vite template's OS dark-mode
   variables (index.css) can't turn the page dark behind dark ink text. */
:root { color-scheme: light; background: var(--paper); color: var(--ink); }
html, body { height: 100%; background: var(--paper); }
#root {
  width: 100%;
  max-width: none;
  min-height: 100%;
  margin: 0;
  padding: 0;
  text-align: left;
  display: block;
}
body {
  display: block;
  min-width: 0;
  width: 100%;
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: var(--body);
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3 { font-family: var(--head); font-weight: 600; margin: 0; letter-spacing: -0.015em; color: var(--ink); }
p { margin: 0; }
button, input, textarea { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--purple); outline-offset: 2px; }

/* buttons */
.btn {
  border: 1px solid var(--line-strong);
  background: var(--surface);
  padding: 9px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: border-color .15s, background .15s;
}
.btn:hover:not(:disabled) { border-color: var(--ink); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.btn.primary { background: var(--purple); border-color: var(--purple); color: #fff; }
.btn.primary:hover:not(:disabled) { background: var(--purple-deep); border-color: var(--purple-deep); }
.btn.danger { color: var(--danger); }
.btn.quiet { border-color: transparent; background: transparent; padding: 6px 8px; color: var(--ink-soft); }
.btn.quiet:hover:not(:disabled) { color: var(--ink); border-color: transparent; }

/* fields */
.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 18px; }
.field label { font-weight: 500; font-size: 14px; }
.field .hint { color: var(--ink-soft); font-size: 13px; }
.hint { color: var(--ink-soft); font-size: 13px; }
.input, .textarea {
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--line-strong);
  border-radius: 6px;
  padding: 10px 12px;
}
.input:focus, .textarea:focus { outline: none; border-color: var(--purple); box-shadow: 0 0 0 3px var(--purple-wash); }
.textarea { resize: vertical; min-height: 260px; line-height: 1.5; }

/* auth */
.auth { min-height: 100vh; width: 100%; display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr); }
.auth-side {
  background: var(--purple);
  color: #f3eeff;
  padding: 56px 56px 48px;
  display: flex; flex-direction: column; justify-content: space-between;
}
.auth-side .mark { font-family: var(--head); font-weight: 700; font-size: 22px; color: #fff; }
.auth-side h1 { font-size: 40px; line-height: 1.1; color: #fff; max-width: 14ch; }
.auth-side p { max-width: 34ch; margin-top: 16px; color: #dcd1fa; }
.auth-main { padding: 56px; display: flex; align-items: center; }
.auth-form { width: 100%; max-width: 360px; }
.auth-form h2 { font-size: 26px; margin-bottom: 24px; }
.auth-switch { margin-top: 20px; color: var(--ink-soft); font-size: 14px; }
.auth-switch button { background: none; border: 0; padding: 0; color: var(--purple); font-weight: 600; cursor: pointer; }
.auth-switch button:hover { text-decoration: underline; }

/* shell */
.shell { min-height: 100vh; width: 100%; display: grid; grid-template-columns: 220px minmax(0, 1fr); }
.side {
  border-right: 1px solid var(--line);
  padding: 28px 20px;
  display: flex; flex-direction: column; gap: 28px;
  position: sticky; top: 0; height: 100vh;
}
.side .mark { font-family: var(--head); font-weight: 700; font-size: 20px; color: var(--purple); padding-left: 10px; }
.nav { display: flex; flex-direction: column; gap: 2px; }
.nav button {
  text-align: left; background: none; border: 0; cursor: pointer;
  padding: 8px 10px; border-radius: 6px; color: var(--ink-soft); font-weight: 500;
  border-left: 3px solid transparent;
}
.nav button:hover { color: var(--ink); }
.nav button.on { color: var(--purple); background: var(--purple-wash); border-left-color: var(--purple); }
.side .who { margin-top: auto; padding: 0 10px; font-size: 13px; color: var(--ink-soft); }
.side .who strong { display: block; color: var(--ink); font-weight: 600; word-break: break-all; }
.side .who button { margin-top: 6px; padding-left: 0; }

.main { padding: 40px 48px 64px; width: 100%; min-width: 0; }
.page-head { margin-bottom: 28px; }
.page-head h2 { font-size: 28px; }
.page-head p { color: var(--ink-soft); margin-top: 4px; max-width: 58ch; }

/* notices */
.notice {
  border: 1px solid var(--line-strong);
  border-left: 3px solid var(--purple);
  background: var(--surface);
  padding: 12px 14px;
  border-radius: 4px;
  margin-bottom: 20px;
  display: flex; gap: 12px; align-items: center; justify-content: space-between;
}
.notice.err { border-left-color: var(--danger); }
.notice.ok { border-left-color: var(--ok); }

/* write view */
.write { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 40px; align-items: start; }
.row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.counter { margin-left: auto; font-size: 13px; color: var(--ink-soft); }

.letter {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 2px 10px 2px 2px;
  min-height: 420px;
  box-shadow: 4px 4px 0 var(--purple-wash);
}
.letter-head { padding: 18px 24px 14px; border-bottom: 1px solid var(--line); }
.letter-head dl { margin: 0; display: grid; grid-template-columns: 64px 1fr; row-gap: 6px; font-size: 14px; }
.letter-head dt { color: var(--ink-soft); }
.letter-head dd { margin: 0; word-break: break-word; }
.letter-head dd.subject { font-weight: 600; }
.letter-body { padding: 22px 24px 28px; white-space: pre-wrap; line-height: 1.65; }
.letter-input {
  width: 100%; border: 0; background: transparent; padding: 2px 4px; margin: -2px -4px;
  font: inherit; font-weight: 600; border-radius: 3px;
}
.letter-input:focus { outline: none; background: var(--purple-wash); }
.letter-textarea {
  display: block; width: 100%; min-height: 300px; border: 0; background: transparent;
  padding: 22px 24px 28px; line-height: 1.65; resize: vertical;
}
.letter-textarea:focus { outline: none; background: #faf8ff; }
.letter-empty { padding: 56px 32px; color: var(--ink-soft); max-width: 36ch; }
.letter-empty strong { display: block; color: var(--ink); font-family: var(--head); font-size: 18px; margin-bottom: 6px; font-weight: 600; }

/* profile / accounts */
.narrow { max-width: 520px; }
.file-box {
  border: 1px dashed var(--line-strong);
  border-radius: 6px;
  padding: 14px;
  background: var(--surface);
  display: flex; align-items: center; gap: 12px; flex-wrap: wrap;
}
.file-box .name { color: var(--ink-soft); font-size: 14px; word-break: break-all; }
.file-box a { color: var(--purple); font-weight: 500; }
.link-sm { color: var(--purple); font-size: 13px; }

.acct {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px 0; border-bottom: 1px solid var(--line);
}
.acct:first-of-type { border-top: 1px solid var(--line); }
.acct small { display: block; color: var(--ink-soft); }

.toast {
  position: fixed; bottom: 24px; right: 24px; max-width: 360px;
  background: var(--ink); color: #fff; padding: 12px 16px; border-radius: 6px;
  font-size: 14px; z-index: 10;
}
.toast.err { background: var(--danger); }

/* history */
.stats { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }
.stat {
  background: var(--surface); border: 1px solid var(--line); border-radius: 2px 10px 2px 2px;
  box-shadow: 4px 4px 0 var(--purple-wash); padding: 16px 22px; min-width: 160px;
}
.stat .num { font-family: var(--head); font-weight: 700; font-size: 34px; color: var(--purple); line-height: 1.1; }
.stat .lbl { color: var(--ink-soft); font-size: 13px; margin-top: 2px; }

.hist { border-top: 1px solid var(--line); }
.hist-item { border-bottom: 1px solid var(--line); }
.hist-row { display: flex; align-items: center; gap: 16px; padding: 14px 4px; }
.hist-main { flex: 1; min-width: 0; }
.hist-subject { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hist-meta { color: var(--ink-soft); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pill {
  font-size: 12px; font-weight: 600; padding: 2px 9px; border-radius: 999px;
  border: 1px solid var(--line-strong); color: var(--ink-soft); background: var(--surface); flex-shrink: 0;
}
.pill.sent { color: var(--ok); border-color: var(--ok); }
.pill.failed { color: var(--danger); border-color: var(--danger); }
.pill.draft { color: var(--purple); border-color: var(--purple); background: var(--purple-wash); }
.hist-open { padding: 0 4px 20px; }
.hist-err { color: var(--danger); font-size: 13px; margin-bottom: 10px; }
.hist-empty { padding: 40px 4px; color: var(--ink-soft); }

.boot { height: 100%; display: grid; place-items: center; color: var(--ink-soft); }

@media (max-width: 900px) {
  .auth { grid-template-columns: 1fr; }
  .auth-side { padding: 28px; gap: 28px; }
  .auth-side h1 { font-size: 30px; }
  .auth-main { padding: 28px; }
  .shell { grid-template-columns: 1fr; }
  .side { position: static; height: auto; flex-direction: row; flex-wrap: wrap; align-items: center; gap: 12px; padding: 14px 16px; border-right: 0; border-bottom: 1px solid var(--line); }
  .nav { flex-direction: row; }
  .side .who { margin: 0 0 0 auto; }
  .side .who strong { display: none; }
  .main { padding: 24px 18px 48px; }
  .write { grid-template-columns: 1fr; gap: 28px; }
}
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
`;

/* ------------------------------------------------------------------ */
/*  Small pieces                                                       */
/* ------------------------------------------------------------------ */

function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef();
  const show = useCallback((msg, kind = "ok") => {
    clearTimeout(timer.current);
    setToast({ msg, kind });
    timer.current = setTimeout(() => setToast(null), 4200);
  }, []);
  const node = toast ? (
    <div className={`toast ${toast.kind === "err" ? "err" : ""}`} role="status">
      {toast.msg}
    </div>
  ) : null;
  return [show, node];
}

/* ------------------------------------------------------------------ */
/*  Auth                                                               */
/* ------------------------------------------------------------------ */

function AuthScreen({ onAuthed }) {
  const [mode, setMode] = useState("login");
  const [f, setF] = useState({ username: "", email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data =
        mode === "login"
          ? await api("/user/login", {
              method: "POST",
              json: { username: f.username, password: f.password },
            })
          : await api("/user/signup", {
              method: "POST",
              json: { username: f.username, email: f.email, password: f.password },
            });
      setAccessToken(data.access_token);
      onAuthed();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <aside className="auth-side">
        <div className="mark">Emailtonic</div>
        <div>
          <h1>Apply to jobs by email, in your own voice.</h1>
          <p>
            Paste a job description. Emailtonic reads your resume, writes the
            email, and sends it from your Gmail.
          </p>
        </div>
        <div />
      </aside>

      <main className="auth-main">
        <form className="auth-form" onSubmit={submit}>
          <h2>{mode === "login" ? "Log in" : "Create your account"}</h2>

          {error && (
            <div className="notice err" role="alert">
              {error}
            </div>
          )}

          <div className="field">
            <label htmlFor="username">
              {mode === "login" ? "Username or email" : "Username"}
            </label>
            <input id="username" className="input" value={f.username} onChange={set("username")} required autoComplete="username" />
          </div>

          {mode === "signup" && (
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" type="email" className="input" value={f.email} onChange={set("email")} required autoComplete="email" />
            </div>
          )}

          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" className="input" value={f.password} onChange={set("password")} required autoComplete={mode === "login" ? "current-password" : "new-password"} />
            {mode === "signup" && <span className="hint">At least 8 characters.</span>}
          </div>

          <button className="btn primary" disabled={busy} style={{ width: "100%" }}>
            {busy ? "One moment..." : mode === "login" ? "Log in" : "Create account"}
          </button>

          <p className="auth-switch">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <button type="button" onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}>
              {mode === "login" ? "Create an account" : "Log in"}
            </button>
          </p>
        </form>
      </main>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Write view                                                         */
/* ------------------------------------------------------------------ */

const MAX_JD = 10000;
const MAX_REF = 500;

function WriteView({ profile, accounts, goto, toast }) {
  const [jd, setJd] = useState("");
  const [to, setTo] = useState("");
  const [ref, setRef] = useState(""); // application focus
  const [draft, setDraft] = useState(null); // {id,status,to,subject,body,from?}
  const [busy, setBusy] = useState(null); // "draft" | "send"
  const [error, setError] = useState("");

  // The backend needs both the extracted resume text and the link
  const hasResume = !!(profile?.resume_link && profile?.resume_text);
  const hasGoogle = accounts.length > 0;
  const ready = jd.trim().length > 0 && jd.length <= MAX_JD;
  const isDraft = draft?.status === "draft";
  const recipient = to.trim() || draft?.to || "";

  async function generate() {
    setBusy("draft");
    setError("");
    try {
      const form = new FormData();
      form.append("job_description", jd);
      if (to.trim()) form.append("to", to.trim());
      if (ref.trim()) form.append("custom_reference", ref.trim());
      setDraft(await api("/send_email/draft", { method: "POST", form }));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    setBusy("send");
    setError("");
    try {
      const form = new FormData();
      form.append("to", recipient);
      form.append("subject", draft.subject);
      form.append("body", draft.body);
      const data = await api(`/send_email/${draft.id}/send`, { method: "POST", form });
      setDraft(data);
      toast(`Sent to ${data.to}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(null);
    }
  }

  const editDraft = (k) => (e) => setDraft({ ...draft, [k]: e.target.value });

  return (
    <>
      <div className="page-head">
        <h2>Write an email</h2>
        <p>Paste the job posting below. If it includes a contact address we'll use it, or you can enter one yourself.</p>
      </div>

      {!hasResume && (
        <div className="notice">
          <span>Add your resume PDF and resume link to your profile before generating emails.</span>
          <button className="btn" onClick={() => goto("profile")}>Open profile</button>
        </div>
      )}
      {hasResume && !hasGoogle && (
        <div className="notice">
          <span>You can generate drafts now. Connect Gmail to send them.</span>
          <button className="btn" onClick={() => goto("accounts")}>Connect Gmail</button>
        </div>
      )}
      {error && <div className="notice err" role="alert">{error}</div>}

      <div className="write">
        <section>
          <div className="field">
            <label htmlFor="jd">Job description</label>
            <textarea id="jd" className="textarea" value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full posting here" />
          </div>

          <div className="field">
            <label htmlFor="to">Send to</label>
            <input id="to" type="email" className="input" value={to} onChange={(e) => setTo(e.target.value)} placeholder="hiring@company.com" />
            <span className="hint">Optional. Overrides any address found in the posting.</span>
          </div>

          <div className="field">
            <label htmlFor="ref">Application focus</label>
            <input
              id="ref"
              className="input"
              value={ref}
              maxLength={MAX_REF}
              onChange={(e) => setRef(e.target.value)}
              placeholder="Backend developer, fresher"
            />
            <span className="hint">
              Optional. Tells the email who you're applying as, even if the posting asks for more experience.
            </span>
          </div>

          <div className="row">
            <button className="btn primary" disabled={!ready || !hasResume || !!busy || ref.length > MAX_REF} onClick={generate}>
              {busy === "draft" ? "Drafting..." : draft ? "Regenerate draft" : "Generate draft"}
            </button>
            <span className="counter" style={jd.length > MAX_JD ? { color: "var(--danger)" } : null}>
              {jd.length.toLocaleString()} / {MAX_JD.toLocaleString()}
            </span>
          </div>
        </section>

        <section aria-live="polite">
          {draft ? (
            <>
              <article className="letter">
                <div className="letter-head">
                  <dl>
                    {draft.from && (<><dt>From</dt><dd>{draft.from}</dd></>)}
                    <dt>To</dt>
                    <dd>
                      {recipient || <em style={{ color: "var(--danger)" }}>No address found. Enter one on the left.</em>}
                    </dd>
                    <dt>Subject</dt>
                    <dd className="subject">
                      {isDraft ? (
                        <input className="letter-input" value={draft.subject} onChange={editDraft("subject")} aria-label="Subject" />
                      ) : (
                        draft.subject
                      )}
                    </dd>
                  </dl>
                </div>
                {isDraft ? (
                  <textarea className="letter-textarea" value={draft.body} onChange={editDraft("body")} aria-label="Email body" />
                ) : (
                  <div className="letter-body">{draft.body}</div>
                )}
              </article>

              {isDraft && (
                <div className="row" style={{ marginTop: 16 }}>
                  <button
                    className="btn primary"
                    disabled={!hasGoogle || !!busy || !recipient || !draft.subject.trim() || !draft.body.trim()}
                    onClick={approve}
                  >
                    {busy === "send" ? "Sending..." : "Approve and send"}
                  </button>
                  {!hasGoogle && <span className="hint">Connect Gmail to send.</span>}
                </div>
              )}
              {draft.status === "sent" && (
                <p className="hint" style={{ marginTop: 16, color: "var(--ok)" }}>Sent.</p>
              )}
            </>
          ) : (
            <div className="letter">
              <div className="letter-empty">
                <strong>Your draft will show up here</strong>
                Generate an email, edit it if you like, then approve it to send exactly what you see.
              </div>
            </div>
          )}
        </section>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Profile view                                                       */
/* ------------------------------------------------------------------ */

function ProfileView({ profile, onSaved, toast }) {
  const [links, setLinks] = useState({
    github_link: profile?.github_link || "",
    leetcode_link: profile?.leetcode_link || "",
    website_link: profile?.website_link || "",
    resume_link: profile?.resume_link || "",
  });
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileRef = useRef();

  const set = (k) => (e) => setLinks({ ...links, [k]: e.target.value });

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const form = new FormData();
      Object.entries(links).forEach(([k, v]) => form.append(k, v));
      if (file) form.append("resume", file);
      await api("/user/profile", { method: profile ? "PUT" : "POST", form });
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
      await onSaved();
      toast("Profile saved");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h2>Profile</h2>
        <p>Your resume and links are what each email is written from.</p>
      </div>

      <form className="narrow" onSubmit={save}>
        {error && <div className="notice err" role="alert">{error}</div>}

        <div className="field">
          <label>Resume PDF</label>
          <div className="file-box">
            <input ref={fileRef} id="resume" type="file" accept="application/pdf" hidden onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <button type="button" className="btn" onClick={() => fileRef.current?.click()}>
              {profile?.resume_text ? "Replace PDF" : "Choose PDF"}
            </button>
            <span className="name">
              {file ? file.name : profile?.resume_text ? "Resume text on file." : "No file chosen"}
            </span>
          </div>
          <span className="hint">PDF only, up to 5 MB, with selectable text. Used to write your emails.</span>
        </div>

        <div className="field">
          <label htmlFor="rl">Resume link</label>
          <input
            id="rl"
            type="url"
            className="input"
            value={links.resume_link}
            onChange={set("resume_link")}
            placeholder="https://drive.google.com/file/d/.../view"
          />
          <span className="hint">
            Paste a Google Drive link. Set sharing to "Anyone with the link can view". Recipients see this link in your email.
          </span>
          {profile?.resume_link && (
            <a className="link-sm" href={profile.resume_link} target="_blank" rel="noreferrer">
              Open saved link
            </a>
          )}
        </div>

        <div className="field">
          <label htmlFor="gh">GitHub</label>
          <input id="gh" className="input" value={links.github_link} onChange={set("github_link")} placeholder="https://github.com/you" />
        </div>
        <div className="field">
          <label htmlFor="lc">LeetCode</label>
          <input id="lc" className="input" value={links.leetcode_link} onChange={set("leetcode_link")} placeholder="https://leetcode.com/u/you" />
        </div>
        <div className="field">
          <label htmlFor="web">Portfolio</label>
          <input id="web" className="input" value={links.website_link} onChange={set("website_link")} placeholder="https://yoursite.dev" />
        </div>

        <button className="btn primary" disabled={busy}>{busy ? "Saving..." : "Save profile"}</button>
      </form>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Accounts view                                                      */
/* ------------------------------------------------------------------ */

function AccountsView({ accounts, reload, toast }) {
  const [busy, setBusy] = useState(false);

  async function connect() {
    setBusy(true);
    try {
      const { auth_url } = await api("/oauth/google/connect");
      window.location.href = auth_url;
    } catch (err) {
      toast(err.message, "err");
      setBusy(false);
    }
  }

  async function disconnect(id) {
    if (!window.confirm("Disconnect this Gmail account? You won't be able to send until you connect again.")) return;
    try {
      await api(`/oauth/accounts/${id}`, { method: "DELETE" });
      await reload();
      toast("Account disconnected");
    } catch (err) {
      toast(err.message, "err");
    }
  }

  return (
    <>
      <div className="page-head">
        <h2>Gmail</h2>
        <p>Emails are sent from the Gmail account you connect here. We only ask for permission to send.</p>
      </div>

      <div className="narrow">
        {accounts.length === 0 ? (
          <div className="notice">
            <span>No Gmail account connected yet.</span>
          </div>
        ) : (
          accounts.map((a) => (
            <div className="acct" key={a.id}>
              <div>
                {a.provider_email}
                {a.created_at && <small>Connected {new Date(a.created_at).toLocaleDateString()}</small>}
              </div>
              <button className="btn danger" onClick={() => disconnect(a.id)}>Disconnect</button>
            </div>
          ))
        )}

        {accounts.length === 0 && (
          <button className="btn primary" onClick={connect} disabled={busy}>
            {busy ? "Opening Google..." : "Connect Gmail"}
          </button>
        )}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  History view                                                       */
/* ------------------------------------------------------------------ */

const HISTORY_LIMIT = 200;

function formatWhen(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit",
  });
}

function HistoryView({ goto }) {
  const [emails, setEmails] = useState(null); // null = loading
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await api(`/send_email/history?limit=${HISTORY_LIMIT}`);
      setEmails(data.emails || []);
    } catch (err) {
      setError(err.message);
      setEmails([]);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const list = emails || [];
  const sentCount = list.filter((m) => m.status === "sent").length;
  const draftCount = list.filter((m) => m.status === "draft").length;
  const capped = list.length >= HISTORY_LIMIT;

  return (
    <>
      <div className="page-head">
        <h2>Sent emails</h2>
        <p>Every email you've drafted or sent. Press Show to read one in full.</p>
      </div>

      {error && (
        <div className="notice err" role="alert">
          <span>{error}</span>
          <button className="btn" onClick={load}>Retry</button>
        </div>
      )}

      <div className="stats">
        <div className="stat">
          <div className="num">{emails === null ? "..." : `${sentCount}${capped ? "+" : ""}`}</div>
          <div className="lbl">Total emails sent</div>
        </div>
        <div className="stat">
          <div className="num">{emails === null ? "..." : draftCount}</div>
          <div className="lbl">Unsent drafts</div>
        </div>
      </div>

      {emails === null ? (
        <p className="hint">Loading...</p>
      ) : list.length === 0 && !error ? (
        <div className="hist-empty">
          Nothing here yet.{" "}
          <button className="btn quiet" onClick={() => goto("write")}>Write your first email</button>
        </div>
      ) : (
        <div className="hist" role="list">
          {list.map((m) => {
            const open = openId === m.id;
            const when = formatWhen(m.sent_at || m.created_at);
            return (
              <div className="hist-item" role="listitem" key={m.id}>
                <div className="hist-row">
                  <div className="hist-main">
                    <div className="hist-subject">{m.subject || "(no subject)"}</div>
                    <div className="hist-meta">
                      {m.to_email ? `To ${m.to_email}` : "No recipient"}
                      {when && ` · ${when}`}
                    </div>
                  </div>
                  <span className={`pill ${m.status}`}>{m.status}</span>
                  <button
                    className="btn"
                    aria-expanded={open}
                    onClick={() => setOpenId(open ? null : m.id)}
                  >
                    {open ? "Hide" : "Show"}
                  </button>
                </div>

                {open && (
                  <div className="hist-open">
                    {m.error && <p className="hist-err">Last error: {m.error}</p>}
                    <article className="letter" style={{ minHeight: 0 }}>
                      <div className="letter-head">
                        <dl>
                          <dt>To</dt>
                          <dd>{m.to_email || "-"}</dd>
                          <dt>Subject</dt>
                          <dd className="subject">{m.subject || "(no subject)"}</dd>
                          <dt>{m.status === "sent" ? "Sent" : "Created"}</dt>
                          <dd>{when || "-"}</dd>
                        </dl>
                      </div>
                      <div className="letter-body">{m.body}</div>
                    </article>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Shell                                                              */
/* ------------------------------------------------------------------ */

function initialView() {
  return window.location.pathname.includes("/settings/integrations") ? "accounts" : "write";
}

function Shell({ user, profile, reloadMe, onLogout }) {
  const [view, setView] = useState(initialView);
  const [accounts, setAccounts] = useState([]);
  const [toast, toastNode] = useToast();

  const loadAccounts = useCallback(async () => {
    try {
      const data = await api("/oauth/accounts?provider=google");
      setAccounts(data.accounts || []);
    } catch {
      setAccounts([]);
    }
  }, []);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);

  // Handle the redirect back from Google (?oauth=success|error)
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const result = p.get("oauth");
    if (!result) return;
    if (result === "success") toast("Gmail connected");
    else toast(`Couldn't connect Gmail (${(p.get("reason") || "unknown").replace(/_/g, " ")})`, "err");
    window.history.replaceState({}, "", "/");
  }, [toast]);

  const tabs = [
    ["write", "Write"],
    ["history", "Sent emails"],
    ["profile", "Profile"],
    ["accounts", "Gmail"],
  ];

  return (
    <div className="shell">
      <aside className="side">
        <div className="mark">Emailtonic</div>
        <nav className="nav" aria-label="Main">
          {tabs.map(([id, label]) => (
            <button key={id} className={view === id ? "on" : ""} aria-current={view === id ? "page" : undefined} onClick={() => setView(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="who">
          Signed in as
          <strong>{user.username}</strong>
          <button className="btn quiet" onClick={onLogout}>Log out</button>
        </div>
      </aside>

      <main className="main">
        {view === "write" && <WriteView profile={profile} accounts={accounts} goto={setView} toast={toast} />}
        {view === "history" && <HistoryView goto={setView} />}
        {view === "profile" && <ProfileView profile={profile} onSaved={reloadMe} toast={toast} />}
        {view === "accounts" && <AccountsView accounts={accounts} reload={loadAccounts} toast={toast} />}
      </main>
      {toastNode}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Root                                                               */
/* ------------------------------------------------------------------ */

export default function App() {
  const [state, setState] = useState("boot"); // boot | out | in
  const [me, setMe] = useState(null);

  const loadMe = useCallback(async () => {
    const data = await api("/user/me");
    setMe(data);
    setState("in");
  }, []);

  // Try to restore the session from the refresh cookie on first load.
  useEffect(() => {
    (async () => {
      try {
        if (await refreshSession()) await loadMe();
        else setState("out");
      } catch {
        setState("out");
      }
    })();
  }, [loadMe]);

  async function logout() {
    try { await api("/user/logout", { method: "POST", retry: false }); } catch { /* ignore */ }
    setAccessToken(null);
    setMe(null);
    setState("out");
  }

  return (
    <>
      <style>{css}</style>
      {state === "boot" && <div className="boot">Loading...</div>}
      {state === "out" && <AuthScreen onAuthed={() => loadMe().catch(() => setState("out"))} />}
      {state === "in" && me && (
        <Shell user={me.user} profile={me.profile} reloadMe={loadMe} onLogout={logout} />
      )}
    </>
  );
}