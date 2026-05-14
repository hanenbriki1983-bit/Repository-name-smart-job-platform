import { useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import './App.css'

const apiBaseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const chatbotReply = (input, jobs) => {
  const text = input.toLowerCase()
  if (text.includes('frontend')) {
    const match = jobs.find((job) => job.title.toLowerCase().includes('frontend'))
    return match
      ? `Try "${match.title}" at ${match.company} in ${match.location}.`
      : 'I could not find a frontend role right now.'
  }

  if (text.includes('python')) {
    const match = jobs.find((job) => job.title.toLowerCase().includes('python'))
    return match
      ? `Try "${match.title}" at ${match.company} in ${match.location}.`
      : 'I could not find a python role right now.'
  }

  if (text.includes('remote')) {
    const remoteJobs = jobs.filter((job) => job.location.toLowerCase().includes('remote'))
    if (remoteJobs.length > 0) {
      return `Remote option: ${remoteJobs[0].title} at ${remoteJobs[0].company}.`
    }
    return 'No remote jobs are listed yet.'
  }

  return 'Ask me about frontend, python, or remote jobs and I will suggest one.'
}

function Layout({ children, isAuthenticated, onLogout }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>Smart Job Platform</h1>
        <nav>
          <NavLink to="/">Home</NavLink>
          {!isAuthenticated && <NavLink to="/login">Login</NavLink>}
          {!isAuthenticated && <NavLink to="/register">Register</NavLink>}
          <NavLink to="/jobs">Jobs</NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
          {isAuthenticated && (
            <button type="button" className="link-btn" onClick={onLogout}>
              Logout
            </button>
          )}
        </nav>
      </header>
      <main>{children}</main>
    </div>
  )
}

function HomePage() {
  return (
    <section className="hero">
      <p className="badge">Find your next career move</p>
      <h2>Jobs, applications, and AI suggestions in one place.</h2>
      <div className="actions">
        <Link to="/jobs" className="btn">
          Browse Jobs
        </Link>
        <Link to="/register" className="btn btn-secondary">
          Create Account
        </Link>
      </div>
    </section>
  )
}

function LoginPage({ onLogin }) {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await fetch(`${apiBaseUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Login failed')
      }

      onLogin(data.token, data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>Login</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn" disabled={loading}>
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </section>
  )
}

function RegisterPage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    try {
      const response = await fetch(`${apiBaseUrl}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Registration failed')
      }

      setMessage('Registration complete. You can login now.')
      setTimeout(() => navigate('/login'), 800)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>Register</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <input type="text" placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}
        <button type="submit" className="btn" disabled={loading}>
          {loading ? 'Creating...' : 'Create Account'}
        </button>
      </form>
    </section>
  )
}

function JobsPage({ token }) {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [applyMessage, setApplyMessage] = useState('')

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/jobs`)
        if (!response.ok) {
          throw new Error('Could not load jobs.')
        }
        const data = await response.json()
        setJobs(data)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchJobs()
  }, [])

  const handleApply = async (jobId) => {
    if (!token) {
      setApplyMessage('Please login first to apply.')
      return
    }

    setApplyMessage('')
    try {
      const response = await fetch(`${apiBaseUrl}/applications`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ job_id: jobId }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Apply failed')
      }

      setApplyMessage('Application submitted successfully.')
    } catch (err) {
      setApplyMessage(err.message)
    }
  }

  return (
    <section className="card">
      <h2>Jobs</h2>
      {loading && <p>Loading jobs...</p>}
      {error && <p className="error">{error}</p>}
      {applyMessage && <p className="success">{applyMessage}</p>}
      <div className="jobs-list">
        {jobs.map((job) => (
          <article className="job-item" key={job.id}>
            <h3>{job.title}</h3>
            <p>{job.company}</p>
            <small>{job.location}</small>
            <div className="job-actions">
              <button type="button" className="btn" onClick={() => handleApply(job.id)}>
                Apply Now
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

function DashboardPage({ currentUser, token, onAuthInvalid }) {
  const [jobs, setJobs] = useState([])
  const [applications, setApplications] = useState([])
  const [verifiedUser, setVerifiedUser] = useState(currentUser)
  const [cvFile, setCvFile] = useState(null)
  const [cvStatus, setCvStatus] = useState(null)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [matches, setMatches] = useState([])
  const [matchesError, setMatchesError] = useState('')
  const [authError, setAuthError] = useState('')
  const [messages, setMessages] = useState([
    { role: 'bot', content: 'Hi! Ask me for frontend, python, or remote jobs.' },
  ])
  const [input, setInput] = useState('')

  useEffect(() => {
    const loadMe = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/auth/me`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Session validation failed')
        }
        setVerifiedUser(data)
        setCvStatus(data.cv_status || null)
      } catch (err) {
        setAuthError(err.message)
        onAuthInvalid()
      }
    }

    loadMe()
  }, [token, onAuthInvalid])

  useEffect(() => {
    const loadJobs = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/jobs`)
        if (!response.ok) return
        const data = await response.json()
        setJobs(data)
      } catch {
        setJobs([])
      }
    }

    const loadApplications = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/applications`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
        if (!response.ok) return
        const data = await response.json()
        setApplications(data)
      } catch {
        setApplications([])
      }
    }

    loadJobs()
    loadApplications()
  }, [token])

  useEffect(() => {
    const loadMatches = async () => {
      try {
        setMatchesError('')
        const response = await fetch(`${apiBaseUrl}/matching`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'Could not load AI matches')
        }
        setMatches(data.items || [])
        setCvStatus(data.cv_status || cvStatus)
      } catch (err) {
        setMatches([])
        setMatchesError(err.message)
      }
    }

    loadMatches()
  }, [token])

  const stats = useMemo(
    () => ({
      totalJobs: jobs.length,
      remoteJobs: jobs.filter((job) => job.location.toLowerCase().includes('remote')).length,
      applicationsCount: applications.length,
    }),
    [jobs, applications]
  )

  const sendMessage = () => {
    if (!input.trim()) return
    const userMessage = { role: 'user', content: input }
    const botMessage = { role: 'bot', content: chatbotReply(input, jobs) }
    setMessages((prev) => [...prev, userMessage, botMessage])
    setInput('')
  }

  const handleCvUpload = async (event) => {
    event.preventDefault()
    if (!cvFile) {
      setUploadError('Please choose a .txt or .pdf file first.')
      return
    }

    setUploadError('')
    setUploadMessage('')

    const formData = new FormData()
    formData.append('file', cvFile)

    try {
      const response = await fetch(`${apiBaseUrl}/profile/cv`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'CV upload failed')
      }

      setUploadMessage(data.message || 'CV uploaded successfully')
      setCvStatus(data.cv_status || null)
      setCvFile(null)

      const matchResponse = await fetch(`${apiBaseUrl}/matching`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const matchData = await matchResponse.json()
      if (!matchResponse.ok) {
        throw new Error(matchData.detail || 'Could not refresh AI matches')
      }
      setMatches(matchData.items || [])
      setMatchesError('')
    } catch (err) {
      setUploadError(err.message)
    }
  }

  return (
    <section className="dashboard-grid">
      <article className="card">
        <h2>Dashboard</h2>
        {authError && <p className="error">{authError}</p>}
        <p>Welcome, {verifiedUser?.name || currentUser?.name || 'User'}</p>
        <p>Email: {verifiedUser?.email || currentUser?.email || '-'}</p>
        <p>Total jobs: {stats.totalJobs}</p>
        <p>Remote jobs: {stats.remoteJobs}</p>
        <p>My applications: {stats.applicationsCount}</p>
        <p>CV uploaded: {cvStatus?.has_cv ? 'Yes' : 'No'}</p>
        {cvStatus?.cv_filename && <p>CV file: {cvStatus.cv_filename}</p>}

        <h3>My Applications</h3>
        <div className="applications-list">
          {applications.length === 0 && <p>No applications yet.</p>}
          {applications.map((item) => (
            <div className="application-item" key={item.id}>
              <strong>{item.job_title}</strong>
              <p>{item.company}</p>
              <small>Status: {item.status}</small>
            </div>
          ))}
        </div>

        <h3>Upload CV</h3>
        <form className="form-grid" onSubmit={handleCvUpload}>
          <input
            type="file"
            accept=".txt,.pdf"
            onChange={(event) => setCvFile(event.target.files?.[0] || null)}
          />
          {uploadError && <p className="error">{uploadError}</p>}
          {uploadMessage && <p className="success">{uploadMessage}</p>}
          <button type="submit" className="btn">
            Upload CV
          </button>
        </form>
      </article>
      <article className="card chatbot">
        <h2>AI Job Assistant</h2>
        <h3>AI Matching</h3>
        {matchesError && <p className="error">{matchesError}</p>}
        <div className="matches-list">
          {matches.length === 0 && !matchesError && <p>No AI matches yet. Upload your CV first.</p>}
          {matches.slice(0, 3).map((item) => (
            <div className="match-item" key={item.job_id}>
              <strong>{item.title}</strong>
              <p>
                {item.company} - {item.location}
              </p>
              <small>Match Score: {item.score}%</small>
              {item.reasons?.map((reason, idx) => (
                <p key={`${item.job_id}-reason-${idx}`}>{reason}</p>
              ))}
            </div>
          ))}
        </div>
        <div className="chat-stream">
          {messages.map((message, index) => (
            <p key={`${message.role}-${index}`} className={`bubble ${message.role}`}>
              {message.content}
            </p>
          ))}
        </div>
        <div className="chat-input">
          <input
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask for a job suggestion"
          />
          <button type="button" className="btn" onClick={sendMessage}>
            Send
          </button>
        </div>
      </article>
    </section>
  )
}

function ProtectedRoute({ isAuthenticated, children }) {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem('auth_token') || '')
  const [currentUser, setCurrentUser] = useState(() => {
    const raw = localStorage.getItem('auth_user')
    return raw ? JSON.parse(raw) : null
  })

  const isAuthenticated = Boolean(token)

  const handleLogin = (newToken, user) => {
    setToken(newToken)
    setCurrentUser(user)
    localStorage.setItem('auth_token', newToken)
    localStorage.setItem('auth_user', JSON.stringify(user))
  }

  const handleLogout = async () => {
    const currentToken = localStorage.getItem('auth_token')
    if (currentToken) {
      try {
        await fetch(`${apiBaseUrl}/auth/logout`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${currentToken}`,
          },
        })
      } catch {
        // Ignore network/logout errors and still clear local session.
      }
    }

    setToken('')
    setCurrentUser(null)
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  }

  const handleAuthInvalid = () => {
    handleLogout()
  }

  return (
    <BrowserRouter>
      <Layout isAuthenticated={isAuthenticated} onLogout={handleLogout}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/jobs" element={<JobsPage token={token} />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute isAuthenticated={isAuthenticated}>
                <DashboardPage currentUser={currentUser} token={token} onAuthInvalid={handleAuthInvalid} />
              </ProtectedRoute>
            }
          />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
