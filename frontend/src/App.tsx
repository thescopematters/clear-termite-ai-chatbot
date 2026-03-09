import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Send, X } from 'lucide-react'
import axios from 'axios'

axios.defaults.baseURL = 'http://localhost:8000'

/* ---------- Types ---------- */
type Message = {
  id: string
  role: 'user' | 'bot'
  content: string
  type?: 'text' | 'table' | 'status'
  data?: any
}

type UserInfo = { id: number; name: string; role: string }

/* ---------- Constants ---------- */
const SUGGESTED_QUESTIONS = [
  'Show my latest inspection report',
  'What repairs are recommended for my property?',
  'Has my termite clearance been issued?',
  'Check status of my payment/invoice',
  'When was my inspection completed?',
]

/* ---------- Helpers ---------- */

/** Turn an array of objects into a markdown table string */
function arrayToMarkdownTable(arr: Record<string, any>[]): string {
  if (!arr.length) return ''
  const keys = Object.keys(arr[0])
  const header = `| ${keys.join(' | ')} |`
  const sep = `| ${keys.map(() => '---').join(' | ')} |`
  const rows = arr.map(
    (r) => `| ${keys.map((k) => (r[k] ?? '—')).join(' | ')} |`,
  )
  return `${header}\n${sep}\n${rows.join('\n')}`
}

/** Derive a CSS colour class from a status string */
function statusColor(status: string): string {
  const s = (status ?? '').toLowerCase()
  if (['clear', 'cleared', 'issued', 'paid', 'completed', 'approved'].some((w) => s.includes(w)))
    return 'badge-green'
  if (['pending', 'scheduled', 'in_escrow', 'in escrow'].some((w) => s.includes(w)))
    return 'badge-yellow'
  if (['denied', 'failed', 'cancelled', 'rejected'].some((w) => s.includes(w)))
    return 'badge-red'
  return 'badge-orange'
}



/* ========== Main App ========== */
function App() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'bot',
      content:
        "👋 Hello! Welcome to Clear Termite.\n\nI’m your virtual assistant and I’m here to help you with inspection updates, payments, repairs, and clearance status.\n\nHow can I assist you today?",
    },
  ])
  const [inputValue, setInputValue] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [user, setUser] = useState<UserInfo | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [showSuggestions, setShowSuggestions] = useState(true)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Fetch demo user token on mount (Dev environment bypass)
  useEffect(() => {
    axios
      .get('/api/dev-token')
      .then((res) => {
        setUser(res.data.user)
        setToken(res.data.access_token)
        setConnectionError(null)
      })
      .catch((err) => {
        console.error('Failed to get dev token', err)
        setConnectionError("Backend API is unreachable. Please ensure the FastAPI server is running and refresh the page.")
      })
  }, [])

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  /* ---------- Send a message ---------- */
  const handleSend = async (text: string) => {
    if (!text.trim()) return
    if (!user || !token) {
      alert("Cannot send message: Not connected to the backend. Please refresh the page.")
      return
    }

    // Hide suggestion chips after first interaction
    setShowSuggestions(false)

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
    }
    setMessages((prev) => [...prev, userMsg])
    setInputValue('')
    setIsTyping(true)

    try {
      const { data: res } = await axios.post(
        '/api/chat',
        { message: text },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      const { message: botText, type, data } = res

      let content = (botText ?? '').trim()

      // Build a proper markdown table from array data
      if (type === 'table' && Array.isArray(data) && data.length > 0) {
        content += '\n\n' + arrayToMarkdownTable(data)
      }
      // For status type, the natural language response from Gemini is sufficient;
      // the structured data is used only for rendering the badge below.

      // Fallback for empty answers
      if (!content) {
        content =
          "No results found for that query — everything might already be clear! 🎉 If you think something's missing, try rephrasing your question."
      }

      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content,
          type: type ?? 'text',
          data,
        },
      ])
    } catch (err) {
      console.error(err)
      setMessages((prev) => [
        ...prev,
        {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content:
            "I'm sorry, I'm having trouble connecting to the system right now. Please try again in a moment.",
        },
      ])
    } finally {
      setIsTyping(false)
    }
  }

  /* ---------- Render ---------- */
  return (
    <>
      {/* ---- Floating Action Button ---- */}
      {!isOpen && (
        <button
          className="fab"
          onClick={() => setIsOpen(true)}
          aria-label="Open customer support chat"
        >
          <img
            src="/cleartermite-icon.png"
            alt="Clear Termite"
            className="fab-icon"
          />
        </button>
      )}

      {/* ---- Chat Panel ---- */}
      {isOpen && (
        <div className="chat-panel" role="dialog" aria-label="Clear Termite Chat">
          {/* Header */}
          <header className="chat-header">
            <div className="header-brand">
              <img
                src="/cleartermite-icon.png"
                alt="Clear Termite logo"
                className="header-logo"
              />
              <span className="brand-name">Clear Termite</span>
            </div>
            <div className="header-right">
              {user && (
                <span className="header-user" aria-label={`Logged in as ${user.name}`}>
                  {user.name}
                </span>
              )}
              <button
                className="close-btn"
                onClick={() => setIsOpen(false)}
                aria-label="Close chat"
              >
                <X size={20} />
              </button>
            </div>
          </header>

          {/* Connection Error Banner */}
          {connectionError && (
            <div style={{ backgroundColor: '#fee2e2', color: '#dc2626', padding: '10px', textAlign: 'center', fontSize: '14px', borderBottom: '1px solid #f87171' }}>
              {connectionError}
            </div>
          )}

          {/* Messages */}
          <main className="chat-messages">
            {messages.map((m) => (
              <div
                key={m.id}
                className={`msg-row ${m.role}`}
                aria-label={`${m.role === 'bot' ? 'Assistant' : 'You'} said`}
              >
                {m.role === 'bot' && (
                  <img src="/cleartermite-icon.png" alt="" className="avatar" />
                )}
                <div className={`bubble ${m.role}`}>
                  {m.role === 'bot' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content}
                    </ReactMarkdown>
                  ) : (
                    <p>{m.content}</p>
                  )}
                  {/* Render inline status badges for status-type responses */}
                  {m.role === 'bot' && m.type === 'status' && m.data && (
                    <div className="status-badges" aria-label="Status information">
                      {(() => {
                        const items = Array.isArray(m.data) ? m.data : [m.data]
                        return items.map((item: any, i: number) => {
                          if (!item || !item.status) return null
                          return (
                            <span
                              key={i}
                              className={`status-badge ${statusColor(item.status)}`}
                              aria-label={`Status: ${item.status}`}
                            >
                              {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
                              {item.amount ? ` - $${Number(item.amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : ''}
                            </span>
                          )
                        })
                      })()}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isTyping && (
              <div className="msg-row bot">
                <img src="/cleartermite-icon.png" alt="" className="avatar" />
                <div className="bubble bot typing-bubble">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </main>

          {/* Footer: suggestions + input */}
          <footer className="chat-footer">
            {showSuggestions && (
              <div className="suggestions" role="list" aria-label="Suggested questions">
                {SUGGESTED_QUESTIONS.map((q, i) => (
                  <button
                    key={i}
                    className="chip"
                    role="listitem"
                    onClick={() => handleSend(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}

            <form
              className="input-row"
              onSubmit={(e) => {
                e.preventDefault()
                handleSend(inputValue)
              }}
            >
              <input
                type="text"
                className="msg-input"
                placeholder="Ask about your inspection, repairs, or clearance…"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                aria-label="Type your message"
              />
              <button
                type="submit"
                className="send-btn"
                disabled={!inputValue.trim()}
                aria-label="Send message"
              >
                <Send size={18} />
              </button>
            </form>
          </footer>
        </div>
      )}
    </>
  )
}

export default App
