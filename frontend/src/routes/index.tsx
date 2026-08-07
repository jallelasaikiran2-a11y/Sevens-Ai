import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Plus,
  Search,
  FolderClosed,
  MessagesSquare,
  Settings,
  PanelLeftClose,
  PanelLeft,
  PanelRight,
  Paperclip,
  Mic,
  ArrowUp,
  Sparkles,
  Check,
  ChevronDown,
  Copy,
  Share2,
  ExternalLink,
  ShieldCheck,
  Brain,
  Activity,
  Route as RouteIcon,
  BookOpen,
  Wrench,
  Layers,
  Command,
  Languages,
  X,
} from "lucide-react";

import {
  LANGUAGES,
  pickGreeting,
  type LanguageCode,
} from "@/lib/sevens-greetings";
import { convo, personalize } from "@/lib/sevens-i18n";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "sevens — AI Intelligence Workspace" },
      {
        name: "description",
        content:
          "The AI that thinks before it answers. sevens orchestrates models and agents, verifies results, and remembers context — delivered as one trusted answer.",
      },
      { property: "og:title", content: "sevens — AI Intelligence Workspace" },
      {
        property: "og:description",
        content:
          "Orchestrated intelligence. Verified answers. Long-term memory. One trusted response.",
      },
    ],
  }),
  component: Workspace,
});

type View = "home" | "conversation";

const LANG_KEY = "sevens.language";
const EXPERT_KEY = "sevens.expert";
const THEME_KEY = "sevens.theme";
const NAME_KEY = "sevens.name";
const DEFAULT_NAME = "Alex";

export type Theme = "light" | "dark";

function Workspace() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(false);
  const [view, setView] = useState<View>("home");
  const [input, setInput] = useState("");
  const [language, setLanguage] = useState<LanguageCode>("en");
  const [expert, setExpert] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>("light");
  const [name, setName] = useState<string>(DEFAULT_NAME);
  const [messages, setMessages] = useState<Array<{ role: string, content: string }>>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Hydrate persisted preferences.
  useEffect(() => {
    try {
      const l = window.localStorage.getItem(LANG_KEY) as LanguageCode | null;
      if (l) setLanguage(l);
      const e = window.localStorage.getItem(EXPERT_KEY);
      if (e === "1") setExpert(true);
      const t = window.localStorage.getItem(THEME_KEY) as Theme | null;
      if (t === "dark" || t === "light") setTheme(t);
      const n = window.localStorage.getItem(NAME_KEY);
      if (n) setName(n);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(LANG_KEY, language);
    } catch {
      /* ignore */
    }
  }, [language]);

  useEffect(() => {
    try {
      window.localStorage.setItem(EXPERT_KEY, expert ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [expert]);

  useEffect(() => {
    try {
      window.localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* ignore */
    }
    const root = document.documentElement;
    if (theme === "dark") root.classList.add("dark");
    else root.classList.remove("dark");
  }, [theme]);

  useEffect(() => {
    try {
      window.localStorage.setItem(NAME_KEY, name);
    } catch {
      /* ignore */
    }
  }, [name]);

  const handleSend = async (text?: string) => {
    const value = (text ?? input).trim();
    if (!value || isLoading) return;
    setInput("");
    setView("conversation");
    if (expert) setRightOpen(true);

    const userMsg = { role: "user", content: value };
    const initialAssistantMsg = { 
      role: "assistant", 
      content: "", 
      plan: null, 
      verification: null, 
      confidence: null,
      execution: [] as any[],
      planning_path: "primary",
      agents_used: [],
      duration_ms: 0,
      phase: "Starting..." 
    };
    
    setMessages([...messages, userMsg, initialAssistantMsg]);
    setIsLoading(true);

    try {
      const apiUrl = import.meta.env.VITE_ORCHESTRATOR_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/api/orchestrate/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: value, expert_mode: expert }),
      });

      if (!res.ok) {
        throw new Error(`Orchestrator returned ${res.status}: ${res.statusText}`);
      }
      if (!res.body) throw new Error("No readable stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let done = false;
      
      let currentMsg = { ...initialAssistantMsg };

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          const lines = chunk.split("\n");
          
          for (const line of lines) {
            if (line.startsWith("data: ") && line !== "data: [DONE]") {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.type === "phase") {
                  currentMsg.phase = data.message;
                  // If content is still empty, set a subtle status indicator
                  if (!currentMsg.content || currentMsg.content.startsWith("[")) {
                    currentMsg.content = `[${data.message}]`;
                  }
                } else if (data.type === "chunk") {
                  // Real-time token streaming
                  if (currentMsg.content.startsWith("[")) {
                    currentMsg.content = "";
                  }
                  currentMsg.content += data.text;
                } else if (data.type === "response_plan") {
                  currentMsg.response_plan = data.outline;
                } else if (data.type === "agent_start") {
                  const existing = currentMsg.agents_used || [];
                  if (!existing.some((a: any) => a.name === data.agent)) {
                    currentMsg.agents_used = [...existing, {
                      name: data.agent,
                      display_name: data.agent,
                      model: data.model,
                      status: "running",
                    }];
                  }
                } else if (data.type === "agent_complete") {
                  const existing = currentMsg.agents_used || [];
                  const updated = existing.map((a: any) => {
                    if (a.name === data.agent) {
                      return {
                        ...a,
                        model: data.model || a.model,
                        provider: data.provider,
                        duration_ms: data.duration_ms,
                        tokens: data.tokens,
                        status: data.success ? "completed" : "failed",
                        success: data.success,
                      };
                    }
                    return a;
                  });
                  if (!updated.some((a: any) => a.name === data.agent)) {
                    updated.push({
                      name: data.agent,
                      display_name: data.agent,
                      model: data.model,
                      provider: data.provider,
                      duration_ms: data.duration_ms,
                      tokens: data.tokens,
                      status: data.success ? "completed" : "failed",
                      success: data.success,
                    });
                  }
                  currentMsg.agents_used = updated;
                } else if (data.type === "plan_ready") {
                  currentMsg.plan = data;
                } else if (data.type === "result") {
                  if (!currentMsg.content || currentMsg.content.startsWith("[")) {
                    currentMsg.content = data.answer ?? data.response;
                  }
                  currentMsg.execution = data.execution ?? [];
                  currentMsg.planning_path = data.planning_path ?? "primary";
                  currentMsg.confidence = data.confidence;
                  currentMsg.verification = data.verification;
                  currentMsg.duration_ms = data.duration_ms;
                  currentMsg.plan = data.plan;
                  currentMsg.agents_used = data.agents_used || currentMsg.agents_used;
                  currentMsg.phase = "Done";
                }
                
                // Update state
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1] = { ...currentMsg };
                  return newMsgs;
                });
                
              } catch (e) {
                console.error("SSE parse error", e, line);
              }
            }
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const newMsgs = [...prev];
        newMsgs[newMsgs.length - 1].content = "Failed to connect to orchestrator.";
        return newMsgs;
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleNew = () => {
    setView("home");
    setRightOpen(false);
    setInput("");
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-ink">
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((v) => !v)}
        onNew={handleNew}
        onOpenSettings={() => setSettingsOpen(true)}
        language={language}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          rightOpen={rightOpen}
          onToggleRight={() => setRightOpen((v) => !v)}
          view={view}
          language={language}
          onLanguageChange={setLanguage}
          expert={expert}
        />

        <main className="relative flex min-h-0 flex-1">
          <section className="flex min-w-0 flex-1 flex-col">
            {view === "home" ? (
              <HomeScreen
                input={input}
                setInput={setInput}
                onSend={handleSend}
                language={language}
                name={name}
              />
            ) : (
              <Conversation
                input={input}
                setInput={setInput}
                onSend={handleSend}
                expert={expert}
                language={language}
                messages={messages}
                isLoading={isLoading}
              />
            )}
          </section>

          <RightPanel open={rightOpen} onClose={() => setRightOpen(false)} expert={expert} messages={messages} isLoading={isLoading} />
        </main>
      </div>

      {settingsOpen && (
        <SettingsSheet
          onClose={() => setSettingsOpen(false)}
          language={language}
          onLanguageChange={setLanguage}
          expert={expert}
          onExpertChange={setExpert}
          theme={theme}
          onThemeChange={setTheme}
          name={name}
          onNameChange={setName}
        />
      )}
    </div>
  );
}

/* ─────────────────────────── Sidebar ─────────────────────────── */

function Sidebar({
  open,
  onToggle,
  onNew,
  onOpenSettings,
  language,
}: {
  open: boolean;
  onToggle: () => void;
  onNew: () => void;
  onOpenSettings: () => void;
  language: LanguageCode;
}) {
  const width = open ? "w-[260px]" : "w-[68px]";
  const langLabel = useMemo(
    () => LANGUAGES.find((l) => l.code === language)?.native ?? "English",
    [language],
  );
  return (
    <aside
      className={`${width} hidden shrink-0 flex-col border-r border-hairline bg-background transition-[width] duration-300 ease-out md:flex`}
    >
      <div className="flex h-16 items-center gap-2.5 px-4">
        <Logo />
        {open && (
          <div className="flex flex-col leading-none">
            <span className="text-[15px] font-semibold tracking-tight">sevens</span>
            <span className="text-[10px] uppercase tracking-[0.14em] text-ink-faint">
              Intelligence
            </span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="ml-auto rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-hover hover:text-ink"
          aria-label="Toggle sidebar"
        >
          {open ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
        </button>
      </div>

      <div className="px-3">
        <button
          onClick={onNew}
          className="group flex w-full items-center gap-3 rounded-2xl border border-hairline bg-surface-elevated px-3 py-2.5 text-sm font-medium text-ink shadow-soft transition-all hover:border-hairline-strong hover:shadow-float"
        >
          <Plus size={16} className="shrink-0" />
          {open && <span>New chat</span>}
          {open && (
            <span className="ml-auto flex items-center gap-0.5 text-[10px] text-ink-faint">
              <Command size={10} />K
            </span>
          )}
        </button>
      </div>

      <nav className="mt-6 flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 vx-scrollbar">
        <NavItem icon={Search} label="Search" open={open} kbd="⌘F" />
        <NavItem icon={FolderClosed} label="Projects" open={open} badge="4" />
        <NavItem icon={MessagesSquare} label="Chat history" open={open} />

        {open && (
          <div className="mt-6 px-2">
            <div className="mb-2 px-2 text-[10px] font-medium uppercase tracking-[0.14em] text-ink-faint">
              Recent
            </div>
            <div className="flex flex-col gap-0.5">
              {RECENTS.map((r) => (
                <button
                  key={r}
                  className="truncate rounded-lg px-2 py-1.5 text-left text-[13px] text-ink-soft transition-colors hover:bg-hover hover:text-ink"
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        )}
      </nav>

      <div className="border-t border-hairline p-2">
        <button
          onClick={onOpenSettings}
          className="flex w-full items-center gap-3 rounded-xl px-2.5 py-2 text-[13px] text-ink-soft transition-colors hover:bg-hover hover:text-ink"
        >
          <Settings size={16} />
          {open && <span>Settings</span>}
          {open && <span className="ml-auto text-[11px] text-ink-faint">{langLabel}</span>}
        </button>

        {open && (
          <div className="mt-2 flex items-center gap-2.5 rounded-xl px-2 py-2">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink text-[11px] font-medium text-primary-foreground">
              AK
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium">Alex Kim</div>
              <div className="truncate text-[11px] text-ink-faint">Pro workspace</div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

const RECENTS = [
  "Q3 competitive landscape",
  "Refactor auth middleware",
  "Draft investor update",
  "Compare vector DBs",
  "Summarize customer calls",
];

function NavItem({
  icon: Icon,
  label,
  open,
  badge,
  kbd,
}: {
  icon: typeof Search;
  label: string;
  open: boolean;
  badge?: string;
  kbd?: string;
}) {
  return (
    <button
      className="group flex items-center gap-3 rounded-xl px-2.5 py-2 text-[13px] text-ink-soft transition-colors hover:bg-hover hover:text-ink"
      title={!open ? label : undefined}
    >
      <Icon size={16} className="shrink-0" />
      {open && <span className="truncate">{label}</span>}
      {open && badge && (
        <span className="ml-auto rounded-md bg-hover px-1.5 py-0.5 text-[10px] text-ink-muted">
          {badge}
        </span>
      )}
      {open && kbd && !badge && (
        <span className="ml-auto text-[10px] text-ink-faint">{kbd}</span>
      )}
    </button>
  );
}

function Logo({ size = 32 }: { size?: number }) {
  return (
    <div
      className="grid shrink-0 place-items-center rounded-xl bg-ink text-primary-foreground"
      style={{ width: size, height: size }}
    >
      <svg
        viewBox="0 0 24 24"
        width={size * 0.6}
        height={size * 0.6}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M4 5l8 14 8-14" />
        <path d="M9 5l3 5 3-5" opacity="0.55" />
      </svg>
    </div>
  );
}

/* ─────────────────────────── Top bar ─────────────────────────── */

function TopBar({
  sidebarOpen,
  onToggleSidebar,
  rightOpen,
  onToggleRight,
  view,
  language,
  onLanguageChange,
  expert,
}: {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  rightOpen: boolean;
  onToggleRight: () => void;
  view: View;
  language: LanguageCode;
  onLanguageChange: (l: LanguageCode) => void;
  expert: boolean;
}) {
  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b border-hairline px-4">
      <button
        onClick={onToggleSidebar}
        className="rounded-lg p-2 text-ink-muted transition-colors hover:bg-hover hover:text-ink md:hidden"
        aria-label="Toggle sidebar"
      >
        {sidebarOpen ? <PanelLeftClose size={16} /> : <PanelLeft size={16} />}
      </button>

      <div className="flex min-w-0 items-center gap-2 text-[13px] text-ink-muted">
        <span className="hidden md:inline">Workspace</span>
        <span className="hidden text-ink-faint md:inline">/</span>
        <span className="truncate font-medium text-ink">
          {view === "home" ? "New session" : "Q3 competitive landscape"}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        <LanguagePicker value={language} onChange={onLanguageChange} />
        {expert && (
          <div className="mx-1 hidden items-center gap-2 rounded-full border border-hairline px-2.5 py-1 text-[11px] text-ink-muted md:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-ink vx-pulse" />
            Expert mode
          </div>
        )}
        <button
          onClick={onToggleRight}
          className={`flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-[12px] transition-colors ${
            rightOpen
              ? "bg-active text-ink"
              : "text-ink-muted hover:bg-hover hover:text-ink"
          }`}
          aria-label="Toggle intelligence panel"
        >
          <PanelRight size={15} />
          <span className="hidden sm:inline">Intelligence</span>
        </button>
      </div>
    </header>
  );
}

function LanguagePicker({
  value,
  onChange,
}: {
  value: LanguageCode;
  onChange: (l: LanguageCode) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = LANGUAGES.find((l) => l.code === value) ?? LANGUAGES[0];

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] text-ink-muted transition-colors hover:bg-hover hover:text-ink"
        aria-label="Language"
      >
        <Languages size={14} />
        <span className="hidden sm:inline">{current.native}</span>
        <ChevronDown size={12} className="text-ink-faint" />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-30 mt-1 max-h-[320px] w-[220px] overflow-y-auto rounded-2xl border border-hairline bg-surface-elevated p-1 shadow-float vx-scrollbar">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                onChange(l.code);
                setOpen(false);
              }}
              className={`flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-[12.5px] transition-colors hover:bg-hover ${
                l.code === value ? "text-ink" : "text-ink-soft"
              }`}
            >
              <span>{l.native}</span>
              <span className="text-[10.5px] text-ink-faint">{l.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────── Home ─────────────────────────── */

function HomeScreen({
  input,
  setInput,
  onSend,
  language,
  name,
}: {
  input: string;
  setInput: (v: string) => void;
  onSend: (text?: string) => void;
  language: LanguageCode;
  name: string;
}) {
  // Generate greeting on client-side only to avoid SSR hydration mismatches
  const [greeting, setGreeting] = useState<string>("Hello, Alex.");

  useEffect(() => {
    const raw = pickGreeting(language);
    setGreeting(personalize(raw, name));
  }, [language, name]);

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6">
      <div className="w-full max-w-[720px]">
        <div className="mb-10 flex justify-center">
          <Logo size={44} />
        </div>

        <h1
          key={greeting}
          className="text-balance text-center text-[40px] font-normal leading-[1.08] tracking-[-0.01em] text-ink md:text-[58px]"
          style={{
            animation: "sevens-stream 0.6s ease-out both",
            fontFamily: '"Playfair Display", "Fraunces", ui-serif, Georgia, serif',
          }}
        >
          {greeting}
        </h1>

        <div className="mt-10">
          <Composer
            value={input}
            onChange={setInput}
            onSend={() => onSend()}
            large
          />
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s.label}
              onClick={() => setInput(s.prompt)}
              className="group flex items-center gap-2 rounded-full border border-hairline bg-surface-elevated px-3.5 py-1.5 text-[12.5px] text-ink-soft shadow-soft transition-all hover:border-hairline-strong hover:text-ink"
            >
              <s.icon size={13} className="text-ink-faint group-hover:text-ink" />
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

const SUGGESTIONS = [
  { label: "Research", prompt: "Research the latest advances in AI orchestration.", icon: BookOpen },
  { label: "Code", prompt: "Refactor this function for readability.", icon: Wrench },
  { label: "Write", prompt: "Draft a concise investor update.", icon: MessagesSquare },
  { label: "Analyze", prompt: "Analyze this quarter's key metrics.", icon: Activity },
  { label: "Plan", prompt: "Plan a 6-week product launch.", icon: Layers },
];

/* ─────────────────────────── Conversation ─────────────────────────── */

function Conversation({
  input,
  setInput,
  onSend,
  expert,
  language,
  messages,
  isLoading,
}: {
  input: string;
  setInput: (v: string) => void;
  onSend: (text?: string) => void;
  expert: boolean;
  language: LanguageCode;
  messages: Array<{ role: string; content: string }>;
  isLoading: boolean;
}) {
  const t = convo(language);
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto vx-scrollbar">
        <div className="mx-auto flex max-w-[760px] flex-col gap-10 px-6 py-12">
          {messages.map((m, i) => 
            m.role === "user" ? (
              <UserMessage key={i}>{m.content}</UserMessage>
            ) : (
              <AssistantMessage key={i} expert={expert} language={language} content={m.content} execution={m.execution} />
            )
          )}
          
          {isLoading && (
            <div className="flex items-center gap-3 text-[13px] text-ink-muted">
              <span className="h-2 w-2 rounded-full bg-ink vx-pulse" />
              sevens is thinking...
            </div>
          )}
        </div>
      </div>

      <div className="px-6 py-4">
        <div className="mx-auto max-w-[760px]">
          <Composer value={input} onChange={setInput} onSend={() => onSend()} />
          <p className="mt-2 text-center text-[11px] text-ink-faint">
            {t.disclaimer}
          </p>
        </div>
      </div>
    </div>
  );
}

function UserMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-3xl rounded-tr-md bg-ink px-5 py-3 text-[15px] leading-relaxed text-primary-foreground">
        {children}
      </div>
    </div>
  );
}

function AssistantMessage({ expert, language, content, execution }: { expert: boolean; language: LanguageCode; content: string; execution?: any[] }) {
  const t = convo(language);
  return (
    <article className="vx-stream flex flex-col gap-5">
      <div className="flex items-center gap-2 text-[11px] text-ink-faint">
        <Logo size={20} />
        <span className="font-medium text-ink-muted">sevens</span>
        {expert && (
          <>
            <span>·</span>
            <span>{t.verifiedAnswer}</span>
            <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-hover px-2 py-0.5 text-ink-soft">
              <ShieldCheck size={11} />
              {t.confidence}
            </span>
          </>
        )}
      </div>

      <div className="text-[15px] leading-[1.75] text-ink-soft whitespace-pre-wrap">
        {content}
      </div>

      {execution && execution.length > 0 && (
        <div className="mt-2 pt-4 border-t border-hairline">
          <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-ink-faint mb-2.5">
            Intelligence Stack
          </div>
          <div className="flex flex-wrap gap-2">
            {execution.map((agent: any, idx: number) => (
              <div key={idx} className="flex flex-col gap-0.5 rounded-lg border border-hairline bg-surface-elevated px-2.5 py-1.5 text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span className={`h-1.5 w-1.5 rounded-full ${agent.status === 'completed' ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="font-medium text-ink">{agent.agent}</span>
                </div>
                <span className="text-ink-muted pl-3">{agent.model} · {agent.provider}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <MessageActions language={language} />
    </article>
  );
}

function SourcesRow({ language }: { language: LanguageCode }) {
  const t = convo(language);
  const sources = t.sources;
  return (
    <div>
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-ink-faint">
        {t.sourcesLabel}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {sources.map((s) => (
          <a
            key={s.title}
            className="group flex flex-col gap-2 rounded-2xl border border-hairline bg-surface-elevated p-3.5 transition-all hover:border-hairline-strong hover:shadow-soft"
          >
            <div className="flex items-center justify-between text-[10px] text-ink-faint">
              <span className="truncate">{s.domain}</span>
              <ExternalLink
                size={11}
                className="opacity-0 transition-opacity group-hover:opacity-100"
              />
            </div>
            <div className="line-clamp-2 text-[13px] font-medium leading-snug text-ink">
              {s.title}
            </div>
            <div className="mt-auto flex items-center gap-2">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-hover">
                <div className="h-full bg-ink" style={{ width: `${s.relevance}%` }} />
              </div>
              <span className="font-mono text-[10px] text-ink-muted">
                {s.relevance}
              </span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}

function MessageActions({ language }: { language: LanguageCode }) {
  const t = convo(language);
  return (
    <div className="flex items-center gap-1 pt-1">
      {[
        { icon: Copy, label: t.copy },
        { icon: Share2, label: t.share },
      ].map(({ icon: Icon, label }) => (
        <button
          key={label}
          className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[12px] text-ink-muted transition-colors hover:bg-hover hover:text-ink"
        >
          <Icon size={13} />
          {label}
        </button>
      ))}
    </div>
  );
}

/* ─────────────── Orchestration timeline (expert only) ─────────────── */

const STAGES = [
  {
    label: "Intent understood",
    detail: "Interpreted as a comparative technical review with cost sensitivity.",
  },
  {
    label: "Memory retrieved",
    detail: "Loaded your previous notes on RAG stack and infra preferences.",
  },
  {
    label: "Research completed",
    detail: "Scanned 24 sources across benchmarks, docs, and post-mortems.",
  },
  {
    label: "Models selected",
    detail: "Routed to Claude for synthesis, DeepSeek for numeric checks.",
  },
  {
    label: "Verification finished",
    detail: "Cross-checked latency claims against two independent benchmarks.",
  },
  { label: "Response generated", detail: "Composed a single trusted answer." },
];

function OrchestrationTimeline() {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-2xl border border-hairline bg-surface-elevated shadow-soft">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
      >
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-primary-foreground">
          <Check size={13} />
        </div>
        <div className="flex-1">
          <div className="text-[13px] font-medium">Orchestration complete</div>
          <div className="text-[11px] text-ink-muted">6 stages · 4 models · 2.4s</div>
        </div>
        <ChevronDown
          size={16}
          className={`text-ink-muted transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && (
        <div className="border-t border-hairline px-4 py-3">
          <ol className="flex flex-col gap-3">
            {STAGES.map((s, i) => (
              <li key={s.label} className="flex gap-3">
                <div className="flex flex-col items-center pt-0.5">
                  <div className="flex h-5 w-5 items-center justify-center rounded-full border border-hairline-strong bg-background">
                    <Check size={11} />
                  </div>
                  {i < STAGES.length - 1 && (
                    <div className="mt-1 h-full w-px flex-1 bg-hairline" />
                  )}
                </div>
                <div className="flex-1 pb-1">
                  <div className="text-[13px] font-medium">{s.label}</div>
                  <div className="text-[12px] leading-relaxed text-ink-muted">
                    {s.detail}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────── Composer ─────────────────────────── */

function Composer({
  value,
  onChange,
  onSend,
  large,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  large?: boolean;
}) {
  const hasText = value.trim().length > 0;
  return (
    <div
      className={`group relative flex flex-col rounded-[28px] border border-hairline bg-transparent transition-all focus-within:border-hairline-strong ${
        large ? "px-4 pt-4 pb-2.5" : "px-3.5 pt-3 pb-2"
      }`}
    >
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
        placeholder="Message sevens…"
        rows={large ? 2 : 1}
        className={`w-full resize-none bg-transparent px-1 py-1 leading-relaxed text-ink placeholder:text-ink-faint focus:outline-none ${
          large ? "text-[16px]" : "text-[15px]"
        }`}
      />
      <div className="mt-1 flex items-center gap-1">
        <button
          title="Attach"
          aria-label="Attach"
          className="flex h-8 w-8 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-hover hover:text-ink"
        >
          <Plus size={17} />
        </button>

        <div className="ml-auto flex items-center gap-1">
          {hasText ? (
            <button
              onClick={onSend}
              className="ml-1 flex h-9 w-9 items-center justify-center rounded-full bg-ink text-primary-foreground transition-all hover:scale-[1.03]"
              aria-label="Send"
            >
              <ArrowUp size={16} />
            </button>
          ) : (
            <>
              <button
                title="Voice"
                aria-label="Voice"
                className="flex h-8 w-8 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-hover hover:text-ink"
              >
                <Mic size={15} />
              </button>
              <button
                title="Live audio"
                aria-label="Live audio"
                className="flex h-8 w-8 items-center justify-center rounded-full text-ink-muted transition-colors hover:bg-hover hover:text-ink"
              >
                <Activity size={15} />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ComposerBtn({
  icon: Icon,
  label,
  text,
}: {
  icon: typeof Paperclip;
  label: string;
  text?: string;
}) {
  return (
    <button
      title={label}
      className="flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-[12px] text-ink-muted transition-colors hover:bg-hover hover:text-ink"
    >
      <Icon size={15} />
      {text && <span>{text}</span>}
    </button>
  );
}

/* ─────────────────────────── Right panel ─────────────────────────── */

function RightPanel({
  open,
  onClose,
  expert,
  messages,
  isLoading,
}: {
  open: boolean;
  onClose: () => void;
  expert: boolean;
  messages?: Array<any>;
  isLoading?: boolean;
}) {
  if (!open) return null;

  const lastAssistantMsg = messages?.slice().reverse().find(m => m.role === "assistant");
  const plan = lastAssistantMsg?.plan;
  const verification = lastAssistantMsg?.verification;
  const duration = lastAssistantMsg?.duration_ms;
  const confidence = lastAssistantMsg?.confidence;
  const execution = lastAssistantMsg?.execution && lastAssistantMsg.execution.length > 0
    ? lastAssistantMsg.execution
    : (lastAssistantMsg?.agents_used || []);
  const planning_path = lastAssistantMsg?.planning_path;
  const responsePlanOutline = lastAssistantMsg?.response_plan;
  const phase = lastAssistantMsg?.phase;

  return (
    <aside
      className="hidden w-[340px] shrink-0 flex-col border-l border-hairline bg-background lg:flex"
      style={{ animation: "sevens-slide-in 0.28s ease-out both" }}
    >
      <div className="flex h-16 items-center gap-2 border-b border-hairline px-4">
        <div className="text-[13px] font-medium">Execution Inspector</div>
        <div className="ml-auto flex items-center gap-2 text-[11px] text-ink-muted">
          {isLoading ? (
            <span className="h-1.5 w-1.5 rounded-full bg-ink vx-pulse" />
          ) : (
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
          )}
          {isLoading ? (phase || "Running...") : "Idle"}
        </div>
        <button
          onClick={onClose}
          className="ml-2 rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-hover hover:text-ink"
          aria-label="Close panel"
        >
          <PanelRight size={15} />
        </button>
      </div>

      <div className="vx-scrollbar flex-1 overflow-y-auto px-4 py-4">
        
        {responsePlanOutline && (
          <PanelSection icon={Brain} title="Response Outline" meta="V4.1">
            <div className="rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[11px] font-mono text-ink-soft whitespace-pre-wrap">
              {responsePlanOutline}
            </div>
          </PanelSection>
        )}

        {confidence !== undefined && (
          <PanelSection icon={Activity} title="Confidence" meta={`${confidence}/100`}>
            <div className="flex flex-col gap-2">
              <div className="rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[12px]">
                <div className="text-ink font-medium">
                  {confidence >= 90 ? "High confidence" : confidence >= 70 ? "Good confidence" : confidence >= 50 ? "Moderate confidence" : "Low confidence"}
                </div>
              </div>
            </div>
          </PanelSection>
        )}

        {(plan || planning_path) && (
          <PanelSection icon={Activity} title="Routing" meta={plan ? `Level ${plan.complexity}` : planning_path}>
            <div className="flex flex-col gap-2">
              {plan && (
                <div className="flex items-center justify-between rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[12px]">
                  <span className="text-ink-soft">Intent</span>
                  <span className="text-ink font-medium">{plan.intent}</span>
                </div>
              )}
              {planning_path && (
                <div className="flex items-center justify-between rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[12px]">
                  <span className="text-ink-soft">Planner</span>
                  <span className="text-ink font-medium capitalize">{planning_path}</span>
                </div>
              )}
            </div>
          </PanelSection>
        )}

        {execution && execution.length > 0 && (
          <PanelSection icon={Layers} title="Agents Executed" meta={`${execution.length} total`}>
            <div className="flex flex-col gap-2">
              {execution.map((agent: any, idx: number) => (
                <div key={`${agent.agent || agent.name}-${idx}`} className="flex flex-col gap-1 rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[12px]">
                  <div className="flex items-center justify-between">
                    <span className="text-ink-soft">{agent.agent || agent.name || agent.display_name}</span>
                    {agent.status === "completed" || agent.success ? (
                      <span className="text-green-600 font-medium">Completed</span>
                    ) : agent.status === "running" ? (
                      <span className="text-amber-500 font-medium animate-pulse">Running...</span>
                    ) : (
                      <span className="text-red-600 font-medium">Failed</span>
                    )}
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-ink-muted font-mono">{agent.model}</span>
                    {agent.duration_ms ? (
                      <span className="text-ink-muted">{agent.duration_ms}ms</span>
                    ) : (
                      <span className="text-ink-muted">{agent.provider || ""}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </PanelSection>
        )}


        {duration && (
          <PanelSection icon={Activity} title="Performance" meta={`${duration}ms`}>
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[12px]">
                <span className="text-ink-soft">Total Latency</span>
                <span className="text-ink font-medium">{duration} ms</span>
              </div>
            </div>
          </PanelSection>
        )}

        {verification && (
          <PanelSection icon={ShieldCheck} title="Verification" meta={verification.layer1 === "passed" ? "Passed" : "Failed"}>
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[12px]">
                <span className="text-ink-soft">Layer 1 (AST/JSON)</span>
                <span className={verification.layer1 === "passed" ? "text-green-600 font-medium" : "text-red-600 font-medium"}>
                  {verification.layer1}
                </span>
              </div>
              <div className="flex items-center justify-between rounded-xl border border-hairline bg-surface-elevated px-3 py-2 text-[12px]">
                <span className="text-ink-soft">Layer 2 (LLM)</span>
                <span className="text-ink-muted font-medium">{verification.layer2}</span>
              </div>
            </div>
          </PanelSection>
        )}
      </div>
    </aside>
  );
}


function PanelSection({
  icon: Icon,
  title,
  meta,
  children,
}: {
  icon: typeof Brain;
  title: string;
  meta?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <section className="mb-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="mb-2 flex w-full items-center gap-2"
      >
        <Icon size={13} className="text-ink-muted" />
        <span className="text-[12px] font-medium">{title}</span>
        {meta && <span className="text-[10.5px] text-ink-faint">· {meta}</span>}
        <ChevronDown
          size={13}
          className={`ml-auto text-ink-faint transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && children}
    </section>
  );
}

function RouterFlow() {
  const nodes = ["Manager", "Claude", "Gemini", "DeepSeek", "GPT", "Verifier", "Answer"];
  return (
    <div className="rounded-2xl border border-hairline bg-surface-elevated p-3">
      <ol className="flex flex-col gap-1.5">
        {nodes.map((n, i) => (
          <li key={n} className="flex items-center gap-2.5">
            <span className="font-mono text-[10px] text-ink-faint">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div className="flex flex-1 items-center justify-between rounded-lg bg-background px-2.5 py-1.5">
              <span className="text-[12px] font-medium">{n}</span>
              {i === nodes.length - 1 ? (
                <Check size={12} className="text-ink" />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-ink/70" />
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ─────────────────────────── Settings sheet ─────────────────────────── */

function SettingsSheet({
  onClose,
  language,
  onLanguageChange,
  expert,
  onExpertChange,
  theme,
  onThemeChange,
  name,
  onNameChange,
}: {
  onClose: () => void;
  language: LanguageCode;
  onLanguageChange: (l: LanguageCode) => void;
  expert: boolean;
  onExpertChange: (v: boolean) => void;
  theme: Theme;
  onThemeChange: (t: Theme) => void;
  name: string;
  onNameChange: (v: string) => void;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ink/20 px-4 backdrop-blur-sm">
      <div
        className="w-full max-w-[520px] rounded-3xl border border-hairline bg-surface-elevated shadow-float"
        style={{ animation: "sevens-stream 0.24s ease-out both" }}
      >
        <div className="flex items-center gap-2 border-b border-hairline px-5 py-4">
          <Settings size={15} className="text-ink-muted" />
          <div className="text-[14px] font-medium">Settings</div>
          <button
            onClick={onClose}
            className="ml-auto rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-hover hover:text-ink"
            aria-label="Close"
          >
            <X size={15} />
          </button>
        </div>

        <div className="flex flex-col gap-6 p-5">
          <SettingRow
            title="Your name"
            description="Personalizes the greeting on your home screen."
          >
            <input
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              placeholder="Alex"
              className="w-[180px] rounded-xl border border-hairline bg-background px-3 py-2 text-[13px] text-ink focus:border-hairline-strong focus:outline-none"
            />
          </SettingRow>

          <div className="h-px bg-hairline" />

          <div>
            <div className="text-[13.5px] font-medium">Appearance</div>
            <div className="mt-1 text-[12px] leading-relaxed text-ink-muted">
              Pick your style. Dark reverses the current palette.
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <ThemeCard
                mode="light"
                active={theme === "light"}
                onSelect={() => onThemeChange("light")}
              />
              <ThemeCard
                mode="dark"
                active={theme === "dark"}
                onSelect={() => onThemeChange("dark")}
              />
            </div>
          </div>

          <div className="h-px bg-hairline" />

          <SettingRow
            title="Expert mode"
            description="Reveal router decisions, verification, memory, tools, and execution timelines. Off by default for a calmer read."
          >
            <Switch checked={expert} onChange={onExpertChange} />
          </SettingRow>

          <div className="h-px bg-hairline" />

          <SettingRow
            title="Language"
            description="Applies to greetings, interface labels, and — where set — response language."
          >
            <select
              value={language}
              onChange={(e) => onLanguageChange(e.target.value as LanguageCode)}
              className="rounded-xl border border-hairline bg-background px-3 py-2 text-[13px] text-ink focus:border-hairline-strong focus:outline-none"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.native} — {l.label}
                </option>
              ))}
            </select>
          </SettingRow>
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-hairline px-5 py-3">
          <button
            onClick={onClose}
            className="rounded-xl bg-ink px-4 py-2 text-[13px] font-medium text-primary-foreground transition-transform hover:scale-[1.02]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

function ThemeCard({
  mode,
  active,
  onSelect,
}: {
  mode: Theme;
  active: boolean;
  onSelect: () => void;
}) {
  const isDark = mode === "dark";
  const bg = isDark ? "#1F1F1F" : "#F6F3DC";
  const line = isDark ? "rgba(246,243,220,0.18)" : "rgba(31,31,31,0.18)";
  const soft = isDark ? "rgba(246,243,220,0.12)" : "rgba(31,31,31,0.10)";
  const ink = isDark ? "#F6F3DC" : "#1F1F1F";
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={active}
      className={`group flex flex-col gap-2 rounded-2xl border p-2 text-left transition-all ${
        active
          ? "border-hairline-strong shadow-float"
          : "border-hairline hover:border-hairline-strong"
      }`}
    >
      <div
        className="relative h-[110px] w-full overflow-hidden rounded-xl"
        style={{ background: bg, border: `1px solid ${line}` }}
      >
        <div
          className="absolute left-2 top-2 h-2 w-2 rounded-full"
          style={{ background: "#e85d3a" }}
        />
        <div className="absolute inset-x-3 top-6 space-y-1.5">
          <div className="h-1.5 w-3/5 rounded-full" style={{ background: soft }} />
          <div className="h-1.5 w-4/5 rounded-full" style={{ background: soft }} />
          <div className="h-1.5 w-2/5 rounded-full" style={{ background: soft }} />
        </div>
        <div
          className="absolute right-0 top-0 h-full w-1/3"
          style={{ background: isDark ? "rgba(246,243,220,0.04)" : "rgba(31,31,31,0.04)" }}
        />
      </div>
      <div className="flex items-center justify-between px-1">
        <span className="text-[13px] font-medium" style={{ color: undefined }}>
          {isDark ? "Dark" : "Light"}
        </span>
        {active && (
          <span
            className="flex h-4 w-4 items-center justify-center rounded-full"
            style={{ background: ink, color: bg }}
          >
            <Check size={10} />
          </span>
        )}
      </div>
    </button>
  );
}

function SettingRow({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
      <div className="min-w-0">
        <div className="text-[13.5px] font-medium">{title}</div>
        <div className="mt-1 text-[12px] leading-relaxed text-ink-muted">
          {description}
        </div>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Switch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative flex h-6 w-10 items-center rounded-full border border-hairline transition-colors ${
        checked ? "bg-ink" : "bg-background"
      }`}
    >
      <span
        className={`absolute h-4 w-4 rounded-full transition-transform ${
          checked
            ? "translate-x-[22px] bg-background"
            : "translate-x-1 bg-ink/70"
        }`}
      />
    </button>
  );
}
