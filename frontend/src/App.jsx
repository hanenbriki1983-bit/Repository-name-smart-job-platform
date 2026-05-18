import { useEffect, useMemo, useRef, useState } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import './App.css'
import heroImage from './assets/hero.png'

const configuredApiUrl = import.meta.env.VITE_API_URL?.trim()
const runtimeHost = typeof window !== 'undefined' ? window.location.hostname : 'localhost'
const localApiCandidates = Array.from(
  new Set([
    `http://${runtimeHost}:8002`,
    `http://${runtimeHost}:8001`,
    `http://${runtimeHost}:8000`,
    'http://127.0.0.1:8002',
    'http://localhost:8002',
    'http://127.0.0.1:8001',
    'http://localhost:8001',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
  ])
)

const I18N = {
  en: {
    appTitle: 'Smart Job Platform',
    home: 'Home',
    login: 'Login',
    register: 'Register',
    jobs: 'Jobs',
    chatbot: 'Chatbot',
    dashboard: 'Dashboard',
    logout: 'Logout',
    heroBadge: 'Find your next career move',
    heroTitle: 'Jobs, applications, and AI suggestions in one place.',
    browseJobs: 'Browse Jobs',
    createAccount: 'Create Account',
    email: 'Email',
    password: 'Password',
    signIn: 'Sign In',
    signingIn: 'Signing in...',
    useDemo: 'Use Demo Login',
    loadingDemo: 'Loading demo...',
    fullName: 'Full name',
    creating: 'Creating...',
    jobsTitle: 'Jobs',
    uploadCv: 'Upload CV',
    searchManual: 'Search manually',
    whatJob: 'What job are you looking for?',
    countryOptional: 'Country (optional)',
    chooseCountryFirst: 'Choose country first',
    noMatchingJobs: 'No matching jobs found.',
    noMatchingJobsBroader: 'No matching jobs found. Try a broader search.',
    showingJobs: 'Showing',
    jobsCountSuffix: 'jobs',
    noFreshMatchingJobs: 'No fresh matches for this search yet. Try a broader title or nearby city.',
    broadenSearch: 'Try Broader Search',
    useAlternativeTitle: 'Use alternative title',
    radius: 'Radius',
    km5: '5 km',
    km10: '10 km',
    km20: '20 km',
    km30: '30 km',
    km50: '50 km',
    km100: '100 km',
    cityOptional: 'City (optional)',
    cityPlaceholder: 'City (optional) e.g. Berlin, Munich, Hamburg',
    search: 'Search',
    searching: 'Searching...',
    advancedFilters: 'Advanced filters (optional)',
    workMode: 'Work mode',
    remote: 'Remote',
    hybrid: 'Hybrid',
    onsite: 'On-site',
    jobType: 'Job type',
    fullTime: 'Full-time',
    partTime: 'Part-time',
    contract: 'Contract',
    internship: 'Internship',
    experienceLevel: 'Experience level',
    junior: 'Junior',
    mid: 'Mid',
    senior: 'Senior',
    loadMore: 'Load More',
    loadingMore: 'Loading more...',
    applyNow: 'Apply Now',
    applyEmployer: 'Apply on employer site',
    matchScore: 'Match Score',
    source: 'Source',
    dashboardTitle: 'Dashboard',
    myApplications: 'My Applications',
    noApplications: 'No applications yet.',
    cvUploaded: 'CV uploaded',
    yes: 'Yes',
    no: 'No',
    quickSearch: 'Quick Search',
    searchAll: 'Search all',
    jobRecommendations: 'Job Recommendations',
    aiMatching: 'AI Matching',
    noMatches: 'No AI matches yet. Upload your CV first.',
    didYouMean: 'Did you mean',
    language: 'Language',
    loadingJobs: 'Loading jobs...',
    uploadCvHint: 'Upload your CV here to enable CV-based matching.',
    goToDashboardUpload: 'Go to Dashboard Upload',
    pleaseLoginApply: 'Please login first to apply.',
    applicationSuccess: 'Application submitted successfully.',
    welcome: 'Welcome',
    totalJobs: 'Total jobs',
    remoteJobs: 'Remote jobs',
    userFallback: 'User',
    status: 'Status',
    cvFile: 'CV file',
    addApiKeysHint: 'Add API keys to see many live jobs.',
    realJobsFetched: 'Real jobs fetched',
    registrationComplete: 'Registration complete. You can login now.',
    loginFailed: 'Login failed',
    demoLoginFailed: 'Demo login failed',
    registrationFailed: 'Registration failed',
    applyFailed: 'Apply failed',
    demoJobNotice: 'This is a sample demo job for presentation only.',
    couldNotLoadJobs: 'Could not load jobs.',
    couldNotLoadAiMatches: 'Could not load AI matches',
    uploadCvButton: 'Upload CV',
    noCityPlaceholder: 'Berlin, Munich, Hamburg...',
    autoRefresh: 'Auto refresh',
    off: 'Off',
    everyMinute: 'Every 1 minute',
    everyHour: 'Every 1 hour',
    everyDay: 'Every 1 day',
    nearbyCitiesHint: 'Nearby cities are included for this location.',
    allCountries: 'All countries',
    chatbotGreeting: 'Hi! I am your Smart Job assistant. Ask me about jobs, CV, or interviews.',
  },
  de: {
    appTitle: 'Smart Job Plattform',
    home: 'Start',
    login: 'Anmelden',
    register: 'Registrieren',
    jobs: 'Jobs',
    chatbot: 'Chatbot',
    dashboard: 'Dashboard',
    logout: 'Abmelden',
    heroBadge: 'Finde deinen nächsten Karriereschritt',
    heroTitle: 'Jobs, Bewerbungen und KI-Empfehlungen an einem Ort.',
    browseJobs: 'Jobs durchsuchen',
    createAccount: 'Konto erstellen',
    email: 'E-Mail',
    password: 'Passwort',
    signIn: 'Anmelden',
    signingIn: 'Anmeldung...',
    useDemo: 'Demo-Login',
    loadingDemo: 'Demo wird geladen...',
    fullName: 'Vollständiger Name',
    creating: 'Erstellen...',
    jobsTitle: 'Jobs',
    uploadCv: 'Lebenslauf hochladen',
    searchManual: 'Manuell suchen',
    whatJob: 'Welchen Job suchst du?',
    countryOptional: 'Land (optional)',
    chooseCountryFirst: 'Wähle zuerst ein Land',
    noMatchingJobs: 'Keine passenden Jobs gefunden.',
    noMatchingJobsBroader: 'Keine passenden Jobs gefunden. Versuche eine breitere Suche.',
    showingJobs: 'Angezeigt werden',
    jobsCountSuffix: 'Jobs',
    noFreshMatchingJobs: 'Keine aktuellen passenden Jobs gefunden.',
    broadenSearch: 'Breitere Suche versuchen',
    useAlternativeTitle: 'Alternativen Titel verwenden',
    radius: 'Radius',
    km5: '5 km',
    km10: '10 km',
    km20: '20 km',
    km30: '30 km',
    km50: '50 km',
    km100: '100 km',
    cityOptional: 'Stadt (optional)',
    cityPlaceholder: 'Stadt (optional) z. B. Berlin, München, Hamburg',
    search: 'Suchen',
    searching: 'Suche...',
    advancedFilters: 'Erweiterte Filter (optional)',
    workMode: 'Arbeitsmodus',
    remote: 'Remote',
    hybrid: 'Hybrid',
    onsite: 'Vor Ort',
    jobType: 'Jobtyp',
    fullTime: 'Vollzeit',
    partTime: 'Teilzeit',
    contract: 'Vertrag',
    internship: 'Praktikum',
    experienceLevel: 'Erfahrungsniveau',
    junior: 'Junior',
    mid: 'Mid',
    senior: 'Senior',
    loadMore: 'Mehr laden',
    loadingMore: 'Lade mehr...',
    applyNow: 'Jetzt bewerben',
    applyEmployer: 'Beim Arbeitgeber bewerben',
    matchScore: 'Match-Score',
    source: 'Quelle',
    dashboardTitle: 'Dashboard',
    myApplications: 'Meine Bewerbungen',
    noApplications: 'Noch keine Bewerbungen.',
    cvUploaded: 'Lebenslauf hochgeladen',
    yes: 'Ja',
    no: 'Nein',
    quickSearch: 'Schnellsuche',
    searchAll: 'Suche in ganz',
    jobRecommendations: 'Job-Empfehlungen',
    aiMatching: 'KI-Matching',
    noMatches: 'Noch keine KI-Matches. Lade zuerst deinen Lebenslauf hoch.',
    didYouMean: 'Meintest du',
    language: 'Sprache',
    loadingJobs: 'Jobs werden geladen...',
    uploadCvHint: 'Lade deinen Lebenslauf hier hoch, um CV-basiertes Matching zu aktivieren.',
    goToDashboardUpload: 'Zum Dashboard-Upload',
    pleaseLoginApply: 'Bitte melde dich zuerst an, um dich zu bewerben.',
    applicationSuccess: 'Bewerbung erfolgreich gesendet.',
    welcome: 'Willkommen',
    totalJobs: 'Gesamtanzahl Jobs',
    remoteJobs: 'Remote-Jobs',
    userFallback: 'Nutzer',
    status: 'Status',
    cvFile: 'CV-Datei',
    addApiKeysHint: 'Füge API-Schlüssel hinzu, um viele Live-Jobs zu sehen.',
    realJobsFetched: 'Live-Jobs geladen',
    registrationComplete: 'Registrierung abgeschlossen. Du kannst dich jetzt anmelden.',
    loginFailed: 'Anmeldung fehlgeschlagen',
    demoLoginFailed: 'Demo-Anmeldung fehlgeschlagen',
    registrationFailed: 'Registrierung fehlgeschlagen',
    applyFailed: 'Bewerbung fehlgeschlagen',
    demoJobNotice: 'Dies ist ein Demo-Beispieljob nur zur Präsentation.',
    couldNotLoadJobs: 'Jobs konnten nicht geladen werden.',
    couldNotLoadAiMatches: 'KI-Matches konnten nicht geladen werden',
    uploadCvButton: 'Lebenslauf hochladen',
    noCityPlaceholder: 'Berlin, München, Hamburg...',
    autoRefresh: 'Automatisch aktualisieren',
    off: 'Aus',
    everyMinute: 'Alle 1 Minute',
    everyHour: 'Alle 1 Stunde',
    everyDay: 'Alle 1 Tag',
    nearbyCitiesHint: 'Nahegelegene Städte werden für diesen Ort einbezogen.',
    allCountries: 'Alle Länder',
    chatbotGreeting: 'Hallo! Ich bin dein Smart-Job-Assistent. Frag mich zu Jobs, Lebenslauf oder Interviews.',
  },
  ar: {
    appTitle: 'منصة الوظائف الذكية',
    home: 'الرئيسية',
    login: 'تسجيل الدخول',
    register: 'إنشاء حساب',
    jobs: 'الوظائف',
    chatbot: 'الدردشة الذكية',
    dashboard: 'لوحة التحكم',
    logout: 'تسجيل الخروج',
    heroBadge: 'اعثر على خطوتك المهنية القادمة',
    heroTitle: 'وظائف وتقديمات وتوصيات ذكية في مكان واحد.',
    browseJobs: 'تصفح الوظائف',
    createAccount: 'إنشاء حساب',
    email: 'البريد الإلكتروني',
    password: 'كلمة المرور',
    signIn: 'دخول',
    signingIn: 'جاري الدخول...',
    useDemo: 'دخول تجريبي',
    loadingDemo: 'جارٍ تحميل التجربة...',
    fullName: 'الاسم الكامل',
    creating: 'جاري الإنشاء...',
    jobsTitle: 'الوظائف',
    uploadCv: 'رفع السيرة الذاتية',
    searchManual: 'بحث يدوي',
    whatJob: 'ما الوظيفة التي تبحث عنها؟',
    countryOptional: 'الدولة (اختياري)',
    chooseCountryFirst: 'اختر الدولة أولاً',
    noMatchingJobs: 'لم يتم العثور على وظائف مطابقة.',
    noMatchingJobsBroader: 'لم يتم العثور على وظائف مطابقة. جرّب بحثًا أوسع.',
    showingJobs: 'عرض',
    jobsCountSuffix: 'وظيفة',
    noFreshMatchingJobs: 'لم يتم العثور على وظائف حديثة مطابقة.',
    broadenSearch: 'جرّب بحثًا أوسع',
    useAlternativeTitle: 'استخدم مسمى بديل',
    radius: 'المسافة',
    km5: '5 كم',
    km10: '10 كم',
    km20: '20 كم',
    km30: '30 كم',
    km50: '50 كم',
    km100: '100 كم',
    cityOptional: 'المدينة (اختياري)',
    cityPlaceholder: 'المدينة (اختياري) مثل برلين، ميونخ، هامبورغ',
    search: 'بحث',
    searching: 'جاري البحث...',
    advancedFilters: 'فلاتر متقدمة (اختياري)',
    workMode: 'نمط العمل',
    remote: 'عن بعد',
    hybrid: 'هجين',
    onsite: 'في الموقع',
    jobType: 'نوع الوظيفة',
    fullTime: 'دوام كامل',
    partTime: 'دوام جزئي',
    contract: 'عقد',
    internship: 'تدريب',
    experienceLevel: 'مستوى الخبرة',
    junior: 'مبتدئ',
    mid: 'متوسط',
    senior: 'خبير',
    loadMore: 'تحميل المزيد',
    loadingMore: 'جاري التحميل...',
    applyNow: 'قدّم الآن',
    applyEmployer: 'التقديم على موقع الشركة',
    matchScore: 'درجة المطابقة',
    source: 'المصدر',
    dashboardTitle: 'لوحة التحكم',
    myApplications: 'طلباتي',
    noApplications: 'لا توجد طلبات بعد.',
    cvUploaded: 'تم رفع السيرة',
    yes: 'نعم',
    no: 'لا',
    quickSearch: 'بحث سريع',
    searchAll: 'بحث في كل',
    jobRecommendations: 'توصيات الوظائف',
    aiMatching: 'مطابقة ذكية',
    noMatches: 'لا توجد نتائج مطابقة بعد. ارفع سيرتك أولاً.',
    didYouMean: 'هل تقصد',
    language: 'اللغة',
    loadingJobs: 'جاري تحميل الوظائف...',
    uploadCvHint: 'ارفع سيرتك الذاتية هنا لتفعيل المطابقة المعتمدة على السيرة.',
    goToDashboardUpload: 'الذهاب إلى رفع السيرة في اللوحة',
    pleaseLoginApply: 'يرجى تسجيل الدخول أولاً للتقديم.',
    applicationSuccess: 'تم إرسال الطلب بنجاح.',
    welcome: 'مرحباً',
    totalJobs: 'إجمالي الوظائف',
    remoteJobs: 'وظائف عن بعد',
    userFallback: 'مستخدم',
    status: 'الحالة',
    cvFile: 'ملف السيرة',
    addApiKeysHint: 'أضف مفاتيح API لعرض عدد كبير من الوظائف الحقيقية.',
    realJobsFetched: 'الوظائف الحقيقية التي تم جلبها',
    registrationComplete: 'اكتمل التسجيل. يمكنك تسجيل الدخول الآن.',
    loginFailed: 'فشل تسجيل الدخول',
    demoLoginFailed: 'فشل تسجيل الدخول التجريبي',
    registrationFailed: 'فشل إنشاء الحساب',
    applyFailed: 'فشل التقديم',
    demoJobNotice: 'هذه وظيفة تجريبية للعرض فقط.',
    couldNotLoadJobs: 'تعذر تحميل الوظائف.',
    couldNotLoadAiMatches: 'تعذر تحميل نتائج المطابقة الذكية',
    uploadCvButton: 'رفع السيرة الذاتية',
    noCityPlaceholder: 'برلين، ميونخ، هامبورغ...',
    autoRefresh: 'تحديث تلقائي',
    off: 'إيقاف',
    everyMinute: 'كل 1 دقيقة',
    everyHour: 'كل 1 ساعة',
    everyDay: 'كل 1 يوم',
    nearbyCitiesHint: 'يتم تضمين المدن القريبة لهذا الموقع.',
    allCountries: 'كل الدول',
    chatbotGreeting: 'مرحبًا! أنا مساعدك في منصة الوظائف الذكية. اسألني عن الوظائف أو السيرة الذاتية أو المقابلات.',
  },
}

const RTL_LANGS = new Set(['ar'])
const tFor = (lang, key) => I18N[lang]?.[key] || I18N.en[key] || key
const POPULAR_JOB_OPTIONS = [
  { value: 'Housekeeping', labels: { en: 'Housekeeping', de: 'Housekeeping', ar: 'خدمة تنظيف / تدبير منزلي' } },
  { value: 'Nurse', labels: { en: 'Nurse', de: 'Krankenpfleger/in', ar: 'ممرض / ممرضة' } },
  { value: 'Nursing Assistant', labels: { en: 'Nursing Assistant', de: 'Pflegehelfer/in', ar: 'مساعدة ممرضة' } },
  { value: 'Case Manager Nurse', labels: { en: 'Case Manager Nurse', de: 'Pflegefallmanager/in', ar: 'مديرة حالة ممرضة' } },
  { value: 'Advanced Practice Nurse', labels: { en: 'Advanced Practice Nurse', de: 'Advanced Practice Nurse', ar: 'ممرضة ممارسة متقدمة' } },
  { value: 'Driver', labels: { en: 'Driver', de: 'Fahrer/in', ar: 'سائق' } },
  { value: 'Security Guard', labels: { en: 'Security Guard', de: 'Sicherheitsmitarbeiter/in', ar: 'حارس أمن' } },
  { value: 'Warehouse Worker', labels: { en: 'Warehouse Worker', de: 'Lagerarbeiter/in', ar: 'عامل مستودع' } },
  { value: 'Cashier', labels: { en: 'Cashier', de: 'Kassierer/in', ar: 'أمين صندوق' } },
  { value: 'Waiter', labels: { en: 'Waiter', de: 'Kellner/in', ar: 'نادل / نادلة' } },
  { value: 'Chef', labels: { en: 'Chef', de: 'Koch / Köchin', ar: 'طباخ / شيف' } },
  { value: 'Sales Assistant', labels: { en: 'Sales Assistant', de: 'Verkäufer/in', ar: 'مساعد مبيعات' } },
  { value: 'Customer Support', labels: { en: 'Customer Support', de: 'Kundensupport', ar: 'دعم العملاء' } },
  { value: 'Electrician', labels: { en: 'Electrician', de: 'Elektriker/in', ar: 'كهربائي' } },
  { value: 'Plumber', labels: { en: 'Plumber', de: 'Installateur/in', ar: 'سباك' } },
  { value: 'Software Engineer', labels: { en: 'Software Engineer', de: 'Softwareentwickler/in', ar: 'مهندس برمجيات' } },
  { value: 'Frontend Developer', labels: { en: 'Frontend Developer', de: 'Frontend-Entwickler/in', ar: 'مطور واجهات أمامية' } },
  { value: 'Data Analyst', labels: { en: 'Data Analyst', de: 'Datenanalyst/in', ar: 'محلل بيانات' } },
  { value: 'Employer Relations Specialist', labels: { en: 'Employer Relations Specialist', de: 'Arbeitgeberbeziehungsmanager/in', ar: 'أصحاب العمل' } },
  { value: 'Job Posting Specialist', labels: { en: 'Job Posting Specialist', de: 'Stellenanzeigen-Spezialist/in', ar: 'إعلانات الوظائف المنشورة' } },
  { value: 'HR Specialist', labels: { en: 'HR Specialist', de: 'HR-Spezialist/in', ar: 'معرفة الموارد البشرية' }, keywords: ['hr', 'human resources', 'resources'] },
  { value: 'Recruiter', labels: { en: 'Recruiter', de: 'Recruiter/in', ar: 'التواصل مع أصحاب العمل' }, keywords: ['hr', 'recruitment', 'talent'] },
  { value: 'Payroll Specialist', labels: { en: 'Payroll Specialist', de: 'Gehaltsabrechnung-Spezialist/in', ar: 'تقرير الرواتب' }, keywords: ['hr', 'payroll', 'salary'] },
]

const JOB_TITLE_ALIASES = {
  'ممرضة': 'Nurse',
  'ممرض': 'Nurse',
  'ممرضة/ممرض': 'Nurse',
  'مساعدة ممرضة': 'Nursing Assistant',
  'مديرة حالة ممرضة': 'Case Manager Nurse',
  'ممرضة ممارسة متقدمة': 'Advanced Practice Nurse',
  'أصحاب العمل': 'Employer Relations Specialist',
  'إعلانات الوظائف المنشورة': 'Job Posting Specialist',
  'معرفة الموارد البشرية': 'HR Specialist',
  'التواصل مع أصحاب العمل': 'Recruiter',
  'تقرير الرواتب': 'Payroll Specialist',
}

const normalizeJobTitleForSearch = (rawTitle) => {
  const text = (rawTitle || '').trim()
  if (!text) return ''
  return JOB_TITLE_ALIASES[text] || text
}

const getLocalJobSuggestions = (text, lang, limit = 8) => {
  const needle = (text || '').trim().toLowerCase()
  if (!needle) return []
  const hits = POPULAR_JOB_OPTIONS.filter((option) => {
    const label = (option.labels?.[lang] || option.labels?.en || option.value || '').toLowerCase()
    const value = (option.value || '').toLowerCase()
    const keywords = (option.keywords || []).join(' ').toLowerCase()
    return label.includes(needle) || value.includes(needle) || keywords.includes(needle)
  }).map((option) => option.value)
  return Array.from(new Set(hits)).slice(0, limit)
}

const getJobLabel = (option, lang) => option?.labels?.[lang] || option?.labels?.en || option?.value || ''

const FALLBACK_GERMANY_CITIES = [
  'Berlin',
  'Hamburg',
  'Munich',
  'München',
  'Düsseldorf',
  'Dusseldorf',
  'Velbert',
  'Essen',
  'Wuppertal',
  'Dresden',
  'Frankfurt',
  'Frankfurt am Main',
  'Cologne',
  'Köln',
  'Stuttgart',
]

const fetchWithFallback = async (path, options = {}) => {
  if (configuredApiUrl) {
    return fetch(`${configuredApiUrl}${path}`, options)
  }

  let lastError
  for (const baseUrl of localApiCandidates) {
    try {
      return await fetch(`${baseUrl}${path}`, options)
    } catch (error) {
      lastError = error
    }
  }
  throw lastError || new Error('Could not connect to backend API')
}

const getAlternativeJobTitleSuggestion = async (rawTitle, lang) => {
  const text = (rawTitle || '').trim()
  if (!text) return ''
  const normalizedCurrent = normalizeJobTitleForSearch(text).toLowerCase()
  const local = getLocalJobSuggestions(text, lang, 8)
  const localAlt = local.find((item) => item && item.toLowerCase() !== normalizedCurrent)
  if (localAlt) return localAlt
  try {
    const response = await fetchWithFallback(`/jobs/suggestions?q=${encodeURIComponent(text)}`)
    if (!response.ok) return ''
    const data = await response.json()
    const remote = Array.isArray(data.items) ? data.items : []
    const remoteAlt = remote.find((item) => item && item.toLowerCase() !== normalizedCurrent)
    return remoteAlt || ''
  } catch {
    return ''
  }
}

const normalizeItems = (rawItems) => {
  if (Array.isArray(rawItems)) return rawItems
  if (rawItems && typeof rawItems === 'object') return Object.values(rawItems)
  return []
}

const isValidApplyUrl = (value) => {
  if (!value || typeof value !== 'string') return false
  const trimmed = value.trim()
  if (!trimmed) return false
  try {
    const parsed = new URL(trimmed)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

const formatPostedAgeLabel = (job) => {
  const postedLabel = (job?.posted_label || '').trim()
  if (postedLabel) return postedLabel
  const days = Number(job?.posted_days)
  if (!Number.isFinite(days) || days < 0) return 'Recently posted'
  if (days === 0) return 'Posted today'
  if (days === 1) return 'Posted 1 day ago'
  if (days < 7) return `Posted ${days} days ago`
  if (days < 14) return 'Posted 1 week ago'
  const weeks = Math.round(days / 7)
  return `Posted ${weeks} weeks ago`
}

const buildOsmEmbedUrl = (lat, lon) => {
  const d = 0.08
  const left = lon - d
  const right = lon + d
  const top = lat + d
  const bottom = lat - d
  return `https://www.openstreetmap.org/export/embed.html?bbox=${left}%2C${bottom}%2C${right}%2C${top}&layer=mapnik&marker=${lat}%2C${lon}`
}

const GERMANY_NEARBY_CITIES = {
  dusseldorf: ['heiligenhaus', 'velbert', 'wuppertal', 'ratingen', 'neuss', 'duisburg'],
  'düsseldorf': ['heiligenhaus', 'velbert', 'wuppertal', 'ratingen', 'neuss', 'duisburg'],
  velbert: ['dusseldorf', 'düsseldorf', 'heiligenhaus', 'wuppertal', 'ratingen', 'essen'],
  heiligenhaus: ['velbert', 'dusseldorf', 'ratingen', 'wülfrath', 'essen'],
  wuppertal: ['velbert', 'dusseldorf', 'solingen', 'remscheid', 'essen'],
  ratingen: ['dusseldorf', 'duisburg', 'essen', 'velbert', 'mettmann'],
  neuss: ['dusseldorf', 'krefeld', 'moenchengladbach', 'köln'],
  duisburg: ['dusseldorf', 'essen', 'oberhausen', 'muelheim', 'krefeld'],
  essen: ['duisburg', 'bochum', 'gelsenkirchen', 'dortmund', 'velbert'],
  berlin: ['potsdam', 'oranienburg', 'bernau', 'teltow'],
  potsdam: ['berlin', 'brandenburg an der havel', 'werder'],
  munich: ['augsburg', 'freising', 'erding', 'dachau'],
  'münchen': ['augsburg', 'freising', 'erding', 'dachau'],
  augsburg: ['münchen', 'munich', 'ulm', 'ingolstadt'],
  hamburg: ['norderstedt', 'pinneberg', 'aharensburg', 'lueneburg'],
  norderstedt: ['hamburg', 'pinneberg', 'elmshorn'],
  frankfurt: ['offenbach', 'darmstadt', 'wiesbaden', 'mainz', 'hanau'],
  'frankfurt am main': ['offenbach', 'darmstadt', 'wiesbaden', 'mainz', 'hanau'],
  stuttgart: ['esslingen', 'ludwigsburg', 'boeblingen', 'heilbronn'],
  cologne: ['köln', 'bonn', 'leverkusen', 'bergisch gladbach', 'troisdorf'],
  bonn: ['köln', 'cologne', 'siegburg', 'troisdorf'],
  dortmund: ['bochum', 'essen', 'hagen', 'unna', 'duisburg'],
  leipzig: ['halle', 'markkleeberg', 'taucha', 'schkeuditz'],
  köln: ['bonn', 'leverkusen', 'bergisch gladbach', 'troisdorf'],
}

const filterJobsClientSide = (items, filters = {}, options = {}) => {
  const title = (filters.job_title || '').trim().toLowerCase()
  const country = (filters.country || '').trim().toLowerCase()
  const city = (filters.city || '').trim().toLowerCase()
  const workMode = (filters.work_mode || '').trim().toLowerCase()
  const exactTitleRequired = options.exactTitleRequired !== false
  const includeNearbyCities = options.includeNearbyCities === true
  const nearbyCities = includeNearbyCities ? (GERMANY_NEARBY_CITIES[city] || []) : []

  return items.filter((job) => {
    const titleBlob = `${job?.title || ''}`.toLowerCase()
    const locationBlob = `${job?.location || ''}`.toLowerCase()
    const modeBlob = `${job?.work_mode || ''} ${job?.description || ''}`.toLowerCase()

    if (title) {
      if (exactTitleRequired && !titleBlob.includes(title)) return false
      if (!exactTitleRequired) {
        const titleTokens = title.split(/\s+/).map((t) => t.trim()).filter((t) => t.length >= 4)
        if (titleTokens.length > 0 && !titleTokens.some((token) => titleBlob.includes(token))) return false
      }
    }
    if (country && !locationBlob.includes(country)) return false
    if (city) {
      const cityMatch = locationBlob.includes(city) || nearbyCities.some((c) => locationBlob.includes(c))
      if (!cityMatch) return false
    }
    if (workMode && !modeBlob.includes(workMode)) return false
    return true
  })
}

const getNearbyCities = (country, city) => {
  const countryValue = (country || '').trim().toLowerCase()
  const cityValue = (city || '').trim().toLowerCase()
  if (!cityValue) return []
  if (!['germany', 'de', 'deutschland'].includes(countryValue)) return []
  return GERMANY_NEARBY_CITIES[cityValue] || []
}

const getShortReason = (job) => {
  if (job?.why_match) return job.why_match
  if (job?.preference_reasons?.length > 0) return job.preference_reasons[0]
  if (job?.reasons?.length > 0) return job.reasons[0]
  return 'General match based on your profile.'
}

function CompanyLogo({ job }) {
  const [imgBroken, setImgBroken] = useState(false)
  const initials = (job?.company_initials || (job?.company || 'CO').split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'CO')
  const targetUrl = (job?.company_website_url || job?.logo_click_url || job?.apply_url || '').trim()
  const clickable = isValidApplyUrl(targetUrl)
  if (job?.company_logo_url && !imgBroken) {
    const img = (
      <img
        className="job-logo"
        src={job.company_logo_url}
        alt={`${job.company || 'Company'} logo`}
        loading="lazy"
        onError={() => setImgBroken(true)}
      />
    )
    if (clickable) {
      return (
        <a href={targetUrl} target="_blank" rel="noopener noreferrer" aria-label={`${job.company || 'Company'} website`}>
          {img}
        </a>
      )
    }
    return img
  }
  const placeholder = <div className="job-logo placeholder" aria-label={`${job?.company || 'Company'} initials`}>{initials}</div>
  if (clickable) {
    return (
      <a href={targetUrl} target="_blank" rel="noopener noreferrer" aria-label={`${job.company || 'Company'} website`}>
        {placeholder}
      </a>
    )
  }
  return placeholder
}

function Layout({ children, isAuthenticated, onLogout, lang, onLangChange }) {
  const t = (key) => tFor(lang, key)
  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>{t('appTitle')}</h1>
        <nav>
          <NavLink to="/">{t('home')}</NavLink>
          {!isAuthenticated && <NavLink to="/login">{t('login')}</NavLink>}
          {!isAuthenticated && <NavLink to="/register">{t('register')}</NavLink>}
          <NavLink to="/jobs">{t('jobs')}</NavLink>
          {isAuthenticated && <NavLink to="/dashboard">{t('dashboard')}</NavLink>}
          {isAuthenticated && <NavLink to="/settings">Settings</NavLink>}
          <NavLink to="/chatbot">{t('chatbot')}</NavLink>
          {isAuthenticated && (
            <button type="button" className="link-btn" onClick={onLogout}>
              {t('logout')}
            </button>
          )}
          <label className="lang-switch">
            <span>{t('language')}</span>
            <select value={lang} onChange={(e) => onLangChange(e.target.value)}>
              <option value="en">EN</option>
              <option value="de">DE</option>
              <option value="ar">AR</option>
            </select>
          </label>
        </nav>
      </header>
      <main>{children}</main>
      <FloatingChatbot lang={lang} />
    </div>
  )
}

function FloatingChatbot({ lang }) {
  const location = useLocation()
  const visible = location.pathname === '/jobs' || location.pathname === '/dashboard'
  const [open, setOpen] = useState(false)
  if (!visible) return null
  return (
    <div className="chat-float-wrap">
      {open && (
        <div className="chat-float-panel">
          <ChatbotPage token={localStorage.getItem('auth_token') || ''} lang={lang} compact />
        </div>
      )}
      <button type="button" className="chat-float-btn" onClick={() => setOpen((prev) => !prev)} aria-label="Open chatbot">
        Chat
      </button>
    </div>
  )
}

function HomePage({ lang }) {
  const t = (key) => tFor(lang, key)
  return (
    <section className="hero">
      <div className="hero-copy">
        <p className="badge">{t('heroBadge')}</p>
        <h2>{t('heroTitle')}</h2>
        <div className="actions">
          <Link to="/jobs" className="btn">
            {t('browseJobs')}
          </Link>
          <Link to="/register" className="btn btn-secondary">
            {t('createAccount')}
          </Link>
        </div>
      </div>
      <img className="hero-image" src={heroImage} alt="Smart Job Platform layered hero graphic" />
    </section>
  )
}

function LoginPage({ onLogin, lang }) {
  const t = (key) => tFor(lang, key)
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await fetchWithFallback('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || t('loginFailed'))
      }

      onLogin(data.token, data.user)
      navigate('/jobs')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleDemoLogin = async () => {
    setError('')
    setDemoLoading(true)

    try {
      const response = await fetchWithFallback('/auth/demo-login', {
        method: 'POST',
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || t('demoLoginFailed'))
      }

      onLogin(data.token, data.user)
      navigate('/jobs')
    } catch (err) {
      setError(err.message)
    } finally {
      setDemoLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>{t('login')}</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <input type="email" placeholder={t('email')} value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          type="password"
          placeholder={t('password')}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="error">{error}</p>}
        <button type="submit" className="btn" disabled={loading}>
          {loading ? t('signingIn') : t('signIn')}
        </button>
        <button type="button" className="btn btn-secondary" onClick={handleDemoLogin} disabled={demoLoading}>
          {demoLoading ? t('loadingDemo') : t('useDemo')}
        </button>
      </form>
    </section>
  )
}

function RegisterPage({ lang }) {
  const t = (key) => tFor(lang, key)
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
      const response = await fetchWithFallback('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || t('registrationFailed'))
      }

      setMessage(t('registrationComplete'))
      setTimeout(() => navigate('/login'), 800)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card">
      <h2>{t('register')}</h2>
      <form className="form-grid" onSubmit={handleSubmit}>
        <input type="text" placeholder={t('fullName')} value={name} onChange={(e) => setName(e.target.value)} required />
        <input type="email" placeholder={t('email')} value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input
          type="password"
          placeholder={t('password')}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p className="error">{error}</p>}
        {message && <p className="success">{message}</p>}
        <button type="submit" className="btn" disabled={loading}>
          {loading ? t('creating') : t('createAccount')}
        </button>
      </form>
    </section>
  )
}

function JobsPage({ token, lang }) {
  const t = (key) => tFor(lang, key)
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [loadingMore, setLoadingMore] = useState(false)
  const [searchMethod, setSearchMethod] = useState('manual')
  const [filters, setFilters] = useState({
    search_text: '',
    country: 'Germany',
    city: '',
    job_title: '',
    radius_km: 20,
    work_mode: '',
    job_type: '',
    experience_level: '',
  })
  const [searchMeta, setSearchMeta] = useState({
    fetched: 0,
    fallback: false,
    apiKeys: false,
    message: '',
    providerWarning: '',
    canBroaden: false,
    hasMore: false,
    total: 0,
    offset: 0,
    limit: 20,
  })
  const [titleSuggestions, setTitleSuggestions] = useState([])
  const [titleCorrectionHint, setTitleCorrectionHint] = useState('')
  const [alternativeTitleSuggestion, setAlternativeTitleSuggestion] = useState('')
  const [cityOptions, setCityOptions] = useState([])
  const [cvFile, setCvFile] = useState(null)
  const [uploadError, setUploadError] = useState('')
  const [uploadMessage, setUploadMessage] = useState('')
  const [showMap, setShowMap] = useState(false)
  const [saveSearchStatus, setSaveSearchStatus] = useState('')
  const [saveWithNotifications, setSaveWithNotifications] = useState(false)
  const nearbyCities = getNearbyCities(filters.country, filters.city)
  const mappableJobs = jobs.filter((job) => Number.isFinite(job.latitude) && Number.isFinite(job.longitude))

  const handleCvUpload = async (event) => {
    event.preventDefault()
    setUploadError('')
    setUploadMessage('')
    if (!token) {
      setUploadError(t('pleaseLoginApply'))
      return
    }
    if (!cvFile) {
      setUploadError('Please choose a file first.')
      return
    }
    const formData = new FormData()
    formData.append('file', cvFile)
    try {
      const response = await fetchWithFallback('/profile/cv', {
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
      setCvFile(null)
      setSearchMethod('manual')
      await runSearch({ append: false })
    } catch (err) {
      setUploadError(err.message || 'CV upload failed')
    }
  }

  const loadTitleSuggestions = async (value) => {
    const text = (value || '').trim()
    const localSuggestions = getLocalJobSuggestions(text, lang, 8)
    if (!text) {
      setTitleSuggestions([])
      setTitleCorrectionHint('')
      return
    }
    try {
      const response = await fetchWithFallback(`/jobs/suggestions?q=${encodeURIComponent(text)}`)
      const data = await response.json()
      if (response.ok) {
        const remote = Array.isArray(data.items) ? data.items : []
        setTitleSuggestions(Array.from(new Set([...localSuggestions, ...remote])).slice(0, 8))
        setTitleCorrectionHint(data.corrected_job_title ? `${t('didYouMean')}: ${data.corrected_job_title}?` : '')
      }
    } catch {
      setTitleSuggestions(localSuggestions)
      setTitleCorrectionHint('')
    }
  }

  const loadCityOptions = async (country, q = '') => {
    try {
      const params = new URLSearchParams()
      if (country) params.set('country', country)
      if (q) params.set('q', q)
      const response = await fetchWithFallback(`/locations/cities?${params.toString()}`)
      if (!response.ok) {
        const needle = (q || '').toLowerCase()
        setCityOptions(FALLBACK_GERMANY_CITIES.filter((c) => !needle || c.toLowerCase().includes(needle)))
        return
      }
      const data = await response.json()
      if (Array.isArray(data.items) && data.items.length > 0) {
        setCityOptions(data.items)
      } else {
        const needle = (q || '').toLowerCase()
        setCityOptions(FALLBACK_GERMANY_CITIES.filter((c) => !needle || c.toLowerCase().includes(needle)))
      }
    } catch {
      const needle = (q || '').toLowerCase()
      setCityOptions(FALLBACK_GERMANY_CITIES.filter((c) => !needle || c.toLowerCase().includes(needle)))
    }
  }

  const runSearch = async ({ append = false, overrideFilters = null } = {}) => {
    const activeFilters = overrideFilters || filters
    const nextOffset = append ? jobs.length : 0
    const effectiveJobTitle = normalizeJobTitleForSearch(activeFilters.job_title)
    if (append) {
      setLoadingMore(true)
    } else {
      setLoading(true)
    }

    try {
      const headers = { 'Content-Type': 'application/json' }
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }
      const response = await fetchWithFallback('/jobs/search', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          ...activeFilters,
          job_title: effectiveJobTitle,
          search_text: (activeFilters.search_text || activeFilters.job_title || '').trim(),
          limit: 20,
          offset: nextOffset,
        }),
      })
      if (!response.ok) {
        throw new Error(t('couldNotLoadJobs'))
      }
      const data = await response.json()
      const incoming = normalizeItems(data.items)
      console.log('[JobsPage] /jobs/search items.length =', incoming.length, 'fetched_jobs_count =', data.fetched_jobs_count)
      let nextJobs = incoming

      // If provider fetch succeeded but ranked items are empty, show raw recent jobs fallback cards.
      if (!append && incoming.length === 0 && Number(data.fetched_jobs_count || 0) > 0) {
        try {
          const rawResponse = await fetchWithFallback('/jobs')
          if (rawResponse.ok) {
            const rawData = await rawResponse.json()
            const rawItems = normalizeItems(rawData)
            const hasRoleQuery = Boolean((activeFilters.job_title || activeFilters.search_text || '').trim())
            const filteredFallback = filterJobsClientSide(rawItems, activeFilters, {
              exactTitleRequired: hasRoleQuery,
              includeNearbyCities: true,
            })
            console.log('[JobsPage] /jobs fallback items.length =', rawItems.length, 'filtered =', filteredFallback.length)
            nextJobs = filteredFallback
          }
        } catch (fallbackErr) {
          console.warn('[JobsPage] /jobs fallback failed', fallbackErr)
        }
      }

      setJobs((prev) => (append ? [...prev, ...nextJobs] : nextJobs))
      if (!append && nextJobs.length === 0) {
        const alternative = await getAlternativeJobTitleSuggestion(activeFilters.job_title, lang)
        setAlternativeTitleSuggestion(alternative)
      } else if (!append) {
        setAlternativeTitleSuggestion('')
      }
      if (!append && nextJobs.length === 0) {
        setSearchMeta((prev) => ({
          ...prev,
          message: data.message || t('noFreshMatchingJobs'),
          providerWarning: data.provider_warning || '',
          canBroaden: Boolean(data.suggested_broaden_search),
          total: 0,
          hasMore: false,
        }))
      }
      setSearchMeta({
        fetched: data.fetched_jobs_count || 0,
        fallback: Boolean(data.used_fallback),
        apiKeys: Boolean(data.api_keys_configured),
        message: data.message || (nextJobs.length === 0 ? t('noFreshMatchingJobs') : ''),
        providerWarning: data.provider_warning || '',
        canBroaden: Boolean(data.suggested_broaden_search),
        hasMore: Boolean(data.has_more),
        total: data.total_available || nextJobs.length,
        offset: data.offset || 0,
        limit: data.limit || 20,
      })
      if (data.corrected_job_title) {
        setTitleCorrectionHint(`${t('didYouMean')}: ${data.corrected_job_title}?`)
      }
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  const runBroaderSearch = async () => {
    const broader = {
      ...filters,
      city: '',
      radius_km: 100,
      work_mode: '',
      job_type: '',
      experience_level: '',
    }
    setFilters(broader)
    await runSearch({ append: false, overrideFilters: broader })
  }

  const applyAlternativeTitleSearch = async () => {
    if (!alternativeTitleSuggestion) return
    const nextFilters = {
      ...filters,
      job_title: alternativeTitleSuggestion,
      search_text: alternativeTitleSuggestion,
    }
    setFilters(nextFilters)
    await runSearch({ append: false, overrideFilters: nextFilters })
  }

  const saveCurrentSearch = async () => {
    if (!token) return
    setSaveSearchStatus('')
    try {
      const response = await fetchWithFallback('/saved-searches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          name: `${(filters.job_title || filters.search_text || 'My').trim()} search`,
          ...filters,
          email_notifications_enabled: saveWithNotifications,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not save search')
      setSaveSearchStatus(data.message || 'Search saved.')
    } catch (err) {
      setSaveSearchStatus(err.message || 'Could not save search')
    }
  }

  useEffect(() => {
    const timerId = setTimeout(() => {
      runSearch({ append: false })
      loadCityOptions('Germany', '')
    }, 0)
    return () => clearTimeout(timerId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  return (
    <section className="card">
      <h2>{t('jobsTitle')}</h2>
      <div className="actions">
        <button
          type="button"
          className={`btn ${searchMethod === 'upload' ? '' : 'btn-secondary'}`}
          onClick={() => setSearchMethod('upload')}
        >
          {t('uploadCv')}
        </button>
        <button
          type="button"
          className={`btn ${searchMethod === 'manual' ? '' : 'btn-secondary'}`}
          onClick={() => setSearchMethod('manual')}
        >
          {t('searchManual')}
        </button>
      </div>

      {searchMethod === 'upload' && (
        <form className="form-grid" onSubmit={handleCvUpload}>
          <p>{t('uploadCvHint')}</p>
          <input
            type="file"
            accept=".txt,.pdf,.doc,.docx,.xls,.xlsx"
            onChange={(event) => setCvFile(event.target.files?.[0] || null)}
          />
          {uploadError && <p className="error">{uploadError}</p>}
          {uploadMessage && <p className="success">{uploadMessage}</p>}
          <button type="submit" className="btn">{t('uploadCvButton')}</button>
        </form>
      )}

      {searchMethod === 'manual' && (
      <form
        className="form-grid search-form"
        onSubmit={(event) => {
          event.preventDefault()
          runSearch({ append: false })
        }}
      >
        <select
          value=""
          onChange={(event) => {
            const value = event.target.value
            if (!value) return
            setFilters((prev) => ({ ...prev, job_title: value }))
            loadTitleSuggestions(value)
          }}
        >
          <option value="">{t('whatJob')}</option>
          {POPULAR_JOB_OPTIONS.map((option) => (
            <option key={`jobs-job-option-${option.value}`} value={option.value}>
              {getJobLabel(option, lang)}
            </option>
          ))}
        </select>
        <input
          type="text"
            placeholder={t('whatJob')}
          list="job-title-suggestions"
          value={filters.job_title}
          onChange={(event) => {
            const value = event.target.value
            setFilters((prev) => ({ ...prev, job_title: value }))
            loadTitleSuggestions(value)
          }}
        />
        <datalist id="job-title-suggestions">
          {titleSuggestions.map((title) => (
            <option key={`job-title-${title}`} value={title} />
          ))}
        </datalist>
        <input type="hidden" value={filters.country || 'Germany'} />
        <input
          type="text"
          placeholder={t('cityPlaceholder')}
          list="jobs-city-suggestions"
          value={filters.city}
          onChange={(event) => {
            const value = event.target.value
            setFilters((prev) => ({ ...prev, city: value }))
            loadCityOptions('Germany', value)
          }}
        />
        <label>
          {t('radius')}
          <select
            value={filters.radius_km}
            onChange={(event) => setFilters((prev) => ({ ...prev, radius_km: Number(event.target.value) || 20 }))}
          >
            <option value={5}>{t('km5')}</option>
            <option value={10}>{t('km10')}</option>
            <option value={20}>{t('km20')}</option>
            <option value={30}>{t('km30')}</option>
            <option value={50}>{t('km50')}</option>
            <option value={100}>{t('km100')}</option>
          </select>
        </label>
        <datalist id="jobs-city-suggestions">
          {cityOptions.map((city) => (
            <option key={`jobs-city-${city}`} value={city} />
          ))}
        </datalist>
        {nearbyCities.length > 0 && (
          <div className="actions">
            {nearbyCities.map((nearCity) => (
              <button
                key={`jobs-near-${nearCity}`}
                type="button"
                className="btn btn-secondary"
                onClick={() => setFilters((prev) => ({ ...prev, city: nearCity }))}
              >
                {nearCity}
              </button>
            ))}
          </div>
        )}
        {(filters.country || '').trim().toLowerCase() === 'germany' && (filters.city || '').trim() && (
          <p className="success">{t('nearbyCitiesHint')}</p>
        )}
        {(filters.country || '').trim() && !(filters.city || '').trim() && (
          <p className="success">{t('searchAll')} {(filters.country || '').trim()}</p>
        )}
        <details>
          <summary>{t('advancedFilters')}</summary>
          <div className="form-grid">
            <select
              value={filters.work_mode}
              onChange={(event) => setFilters((prev) => ({ ...prev, work_mode: event.target.value }))}
            >
                <option value="">{t('workMode')}</option>
                <option value="remote">{t('remote')}</option>
                <option value="hybrid">{t('hybrid')}</option>
                <option value="on-site">{t('onsite')}</option>
            </select>
            <select
              value={filters.job_type}
              onChange={(event) => setFilters((prev) => ({ ...prev, job_type: event.target.value }))}
            >
                <option value="">{t('jobType')}</option>
                <option value="full-time">{t('fullTime')}</option>
                <option value="part-time">{t('partTime')}</option>
                <option value="contract">{t('contract')}</option>
                <option value="internship">{t('internship')}</option>
            </select>
            <select
              value={filters.experience_level}
              onChange={(event) => setFilters((prev) => ({ ...prev, experience_level: event.target.value }))}
            >
                <option value="">{t('experienceLevel')}</option>
                <option value="junior">{t('junior')}</option>
                <option value="mid">{t('mid')}</option>
                <option value="senior">{t('senior')}</option>
            </select>
          </div>
        </details>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>
      )}
      {loading && <p>{t('loadingJobs')}</p>}
      {error && <p className="error">{error}</p>}
      {titleCorrectionHint && <p className="success">{titleCorrectionHint}</p>}
      {!loading && !error && (
        <p>
          {jobs.length > 0
            ? `${t('showingJobs')} ${jobs.length} ${t('jobsCountSuffix')}`
            : (searchMeta.message || t('noMatchingJobsBroader'))}
        </p>
      )}
      {!loading && !error && jobs.length === 0 && searchMeta.canBroaden && (
        <div className="job-actions">
          <button type="button" className="btn btn-secondary" onClick={runBroaderSearch}>
            {t('broadenSearch')}
          </button>
        </div>
      )}
      {!loading && !error && jobs.length === 0 && alternativeTitleSuggestion && (
        <div className="job-actions">
          <button type="button" className="btn btn-secondary" onClick={applyAlternativeTitleSearch}>
            {t('useAlternativeTitle')}: {alternativeTitleSuggestion}
          </button>
        </div>
      )}
      {token && (
        <div className="actions">
          <label>
            <input
              type="checkbox"
              checked={saveWithNotifications}
              onChange={(e) => setSaveWithNotifications(Boolean(e.target.checked))}
            />
            Enable email notifications for this saved search
          </label>
          <button type="button" className="btn btn-secondary" onClick={saveCurrentSearch}>Save this search</button>
          {saveSearchStatus && <p className="success">{saveSearchStatus}</p>}
        </div>
      )}
      <div className="actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setShowMap((prev) => !prev)}
          disabled={mappableJobs.length === 0}
        >
          {showMap ? 'Hide map' : 'Show map (optional)'}
        </button>
      </div>
      {showMap && mappableJobs.length > 0 && (
        <section className="card map-panel">
          <h3>Map view</h3>
          <iframe
            title="Job map"
            src={buildOsmEmbedUrl(mappableJobs[0].latitude, mappableJobs[0].longitude)}
            className="map-frame"
            loading="lazy"
          />
          <div className="map-list">
            {mappableJobs.slice(0, 8).map((job) => {
              const origin = encodeURIComponent(filters.city || 'Germany')
              const destination = encodeURIComponent(`${job.latitude},${job.longitude}`)
              const routeUrl = `https://www.google.com/maps/dir/?api=1&origin=${origin}&destination=${destination}&travelmode=driving`
              return (
                <div key={`map-${job.job_id || job.id}-${job.title}`} className="match-item">
                  <strong>{job.title}</strong>
                  <p>{job.company} - {job.city || job.location}</p>
                  {job.distance_label && <small>{job.distance_label}</small>}
                  <a href={routeUrl} target="_blank" rel="noopener noreferrer">Open route</a>
                </div>
              )
            })}
          </div>
        </section>
      )}
      <div className="jobs-list">
        {jobs.map((job) => (
          <article className="job-item" key={`${job.job_id || 'job'}-${job.external_id || job.id || job.title}`}>
            <CompanyLogo job={job} />
            <h3>{job.title}</h3>
            <p>{job.company}</p>
            <small>{job.city || job.location}</small>
            {job.source && <small>{t('source')}: {job.source}</small>}
            {job.work_mode && <small>{job.work_mode}</small>}
            {job.distance_label && <small>{job.distance_label}</small>}
            <small>{formatPostedAgeLabel(job)}</small>
            {'score' in job && <p>{t('matchScore')}: {job.score}%</p>}
            <p>{getShortReason(job)}</p>
            {isValidApplyUrl(job.apply_url) && !job.is_sample_demo && (
              <div className="job-actions">
                <a className="btn" href={job.apply_url} target="_blank" rel="noopener noreferrer">
                  {t('applyNow')}
                </a>
              </div>
            )}
          </article>
        ))}
      </div>
      {searchMeta.hasMore && (
        <div className="job-actions">
          <button type="button" className="btn" onClick={() => runSearch({ append: true })} disabled={loadingMore}>
            {loadingMore ? t('loadingMore') : t('loadMore')}
          </button>
        </div>
      )}
    </section>
  )
}

// eslint-disable-next-line no-unused-vars
function DashboardPage({ currentUser, token, onAuthInvalid, lang }) {
  const t = (key) => tFor(lang, key)
  const [, setJobs] = useState([])
  const [applications, setApplications] = useState([])
  const [verifiedUser, setVerifiedUser] = useState(currentUser)
  const [cvFile, setCvFile] = useState(null)
  const [cvStatus, setCvStatus] = useState(null)
  const [uploadMessage, setUploadMessage] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [preferences, setPreferences] = useState({
    search_text: '',
    country: 'Germany',
    city: '',
    job_title: '',
    radius_km: 20,
    work_mode: '',
    job_type: '',
    experience_level: '',
  })
  const [preferencesError, setPreferencesError] = useState('')
  const [matches, setMatches] = useState([])
  const [matchesError, setMatchesError] = useState('')
  const [matchesLoading, setMatchesLoading] = useState(false)
  const [matchesLoadingMore, setMatchesLoadingMore] = useState(false)
  const [searchMethod, setSearchMethod] = useState('manual')
  const [matchSearchMeta, setMatchSearchMeta] = useState({
    fetched: 0,
    fallback: false,
    apiKeys: false,
    message: '',
    providerWarning: '',
    canBroaden: false,
    hasMore: false,
    total: 0,
    offset: 0,
    limit: 20,
  })
  const [dashboardTitleSuggestions, setDashboardTitleSuggestions] = useState([])
  const [dashboardCorrectionHint, setDashboardCorrectionHint] = useState('')
  const [dashboardAlternativeTitleSuggestion, setDashboardAlternativeTitleSuggestion] = useState('')
  const [authError, setAuthError] = useState('')
  const [careerPlan, setCareerPlan] = useState(null)
  const [careerPlanLoading, setCareerPlanLoading] = useState(false)
  const [careerPlanError, setCareerPlanError] = useState('')
  const [cityOptions, setCityOptions] = useState([])
  const dashboardNearbyCities = getNearbyCities(preferences.country, preferences.city)

  const loadDashboardTitleSuggestions = async (value) => {
    const text = (value || '').trim()
    const localSuggestions = getLocalJobSuggestions(text, lang, 8)
    if (!text) {
      setDashboardTitleSuggestions([])
      setDashboardCorrectionHint('')
      return
    }
    try {
      const response = await fetchWithFallback(`/jobs/suggestions?q=${encodeURIComponent(text)}`)
      const data = await response.json()
      if (response.ok) {
        const remote = Array.isArray(data.items) ? data.items : []
        setDashboardTitleSuggestions(Array.from(new Set([...localSuggestions, ...remote])).slice(0, 8))
        setDashboardCorrectionHint(data.corrected_job_title ? `${t('didYouMean')}: ${data.corrected_job_title}?` : '')
      }
    } catch {
      setDashboardTitleSuggestions(localSuggestions)
      setDashboardCorrectionHint('')
    }
  }

  const loadCityOptions = async (country, q = '') => {
    try {
      const params = new URLSearchParams()
      if (country) params.set('country', country)
      if (q) params.set('q', q)
      const response = await fetchWithFallback(`/locations/cities?${params.toString()}`)
      if (!response.ok) {
        const needle = (q || '').toLowerCase()
        setCityOptions(FALLBACK_GERMANY_CITIES.filter((c) => !needle || c.toLowerCase().includes(needle)))
        return
      }
      const data = await response.json()
      if (Array.isArray(data.items) && data.items.length > 0) {
        setCityOptions(data.items)
      } else {
        const needle = (q || '').toLowerCase()
        setCityOptions(FALLBACK_GERMANY_CITIES.filter((c) => !needle || c.toLowerCase().includes(needle)))
      }
    } catch {
      const needle = (q || '').toLowerCase()
      setCityOptions(FALLBACK_GERMANY_CITIES.filter((c) => !needle || c.toLowerCase().includes(needle)))
    }
  }

  const runDashboardSearch = async ({ append = false, overridePreferences = null } = {}) => {
    const activePreferences = overridePreferences || preferences
    const effectiveJobTitle = normalizeJobTitleForSearch(activePreferences.job_title)
    const nextOffset = append ? matches.length : 0
    if (append) {
      setMatchesLoadingMore(true)
    } else {
      setMatchesLoading(true)
    }
    try {
      setMatchesError('')
      const response = await fetchWithFallback('/jobs/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...activePreferences,
          job_title: effectiveJobTitle,
          search_text: (activePreferences.search_text || activePreferences.job_title || '').trim(),
          limit: 20,
          offset: nextOffset,
        }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || t('couldNotLoadAiMatches'))
      }
      const incoming = normalizeItems(data.items)
      console.log('[Dashboard] /jobs/search items.length =', incoming.length, 'fetched_jobs_count =', data.fetched_jobs_count)
      let nextMatches = incoming

      if (!append && incoming.length === 0 && Number(data.fetched_jobs_count || 0) > 0) {
        try {
          const rawResponse = await fetchWithFallback('/jobs')
          if (rawResponse.ok) {
            const rawData = await rawResponse.json()
            const rawItems = normalizeItems(rawData)
            const filteredFallback = filterJobsClientSide(rawItems, activePreferences || {}, { exactTitleRequired: false, includeNearbyCities: true })
            console.log('[Dashboard] /jobs fallback items.length =', rawItems.length, 'filtered =', filteredFallback.length)
            nextMatches = filteredFallback
          }
        } catch (fallbackErr) {
          console.warn('[Dashboard] /jobs fallback failed', fallbackErr)
        }
      }

      setMatches((prev) => (append ? [...prev, ...nextMatches] : nextMatches))
      if (!append && nextMatches.length === 0) {
        const alternative = await getAlternativeJobTitleSuggestion(activePreferences.job_title, lang)
        setDashboardAlternativeTitleSuggestion(alternative)
      } else if (!append) {
        setDashboardAlternativeTitleSuggestion('')
      }
      setMatchSearchMeta({
        fetched: data.fetched_jobs_count || 0,
        fallback: Boolean(data.used_fallback),
        apiKeys: Boolean(data.api_keys_configured),
        message: data.message || (nextMatches.length === 0 ? t('noFreshMatchingJobs') : ''),
        providerWarning: data.provider_warning || '',
        canBroaden: Boolean(data.suggested_broaden_search),
        hasMore: Boolean(data.has_more),
        total: data.total_available || nextMatches.length,
        offset: data.offset || 0,
        limit: data.limit || 20,
      })
      if (data.corrected_job_title) {
        setDashboardCorrectionHint(`${t('didYouMean')}: ${data.corrected_job_title}?`)
      }
    } catch (err) {
      if (!append) {
        setMatches([])
      }
      setMatchesError(err.message)
    } finally {
      setMatchesLoading(false)
      setMatchesLoadingMore(false)
    }
  }

  useEffect(() => {
    const loadMe = async () => {
      try {
        const response = await fetchWithFallback('/auth/me', {
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
        setPreferences({
          search_text: '',
          country: data.preferences?.country || '',
          city: data.preferences?.city || '',
          job_title: data.preferences?.job_title || '',
          work_mode: data.preferences?.work_mode || '',
          job_type: data.preferences?.job_type || '',
          experience_level: data.preferences?.experience_level || '',
        })
        loadCityOptions('Germany', data.preferences?.city || '')
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
        const response = await fetchWithFallback('/jobs')
        if (!response.ok) return
        const data = await response.json()
        setJobs(data)
      } catch {
        setJobs([])
      }
    }

    const loadApplications = async () => {
      try {
        const response = await fetchWithFallback('/applications', {
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
    const timerId = setTimeout(() => {
      runDashboardSearch({ append: false })
    }, 0)
    return () => clearTimeout(timerId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const stats = useMemo(
    () => ({
      totalJobs: matchSearchMeta.total || matches.length,
      remoteJobs: matches.filter((job) => `${job.location || ''}`.toLowerCase().includes('remote')).length,
      applicationsCount: applications.length,
    }),
    [matches, matchSearchMeta.total, applications]
  )

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
      const response = await fetchWithFallback('/profile/cv', {
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

      await runDashboardSearch({ append: false })
    } catch (err) {
      setUploadError(err.message)
    }
  }

  const handleModeSearch = async (event) => {
    event.preventDefault()
    setPreferencesError('')
    await runDashboardSearch({ append: false, overridePreferences: preferences })
  }

  const runDashboardBroaderSearch = async () => {
    const broader = {
      ...preferences,
      city: '',
      radius_km: 100,
      work_mode: '',
      job_type: '',
      experience_level: '',
    }
    setPreferences(broader)
    await runDashboardSearch({ append: false, overridePreferences: broader })
  }

  const applyDashboardAlternativeTitleSearch = async () => {
    if (!dashboardAlternativeTitleSuggestion) return
    const nextPreferences = {
      ...preferences,
      job_title: dashboardAlternativeTitleSuggestion,
      search_text: dashboardAlternativeTitleSuggestion,
    }
    setPreferences(nextPreferences)
    await runDashboardSearch({ append: false, overridePreferences: nextPreferences })
  }

  const generateCareerPlan = async () => {
    setCareerPlanError('')
    setCareerPlanLoading(true)
    try {
      const response = await fetchWithFallback('/career/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          target_role: preferences.job_title || '',
          target_city: preferences.city || 'Germany',
          language: lang,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not generate career plan')
      setCareerPlan(data)
    } catch (err) {
      setCareerPlanError(err.message || 'Could not generate career plan')
    } finally {
      setCareerPlanLoading(false)
    }
  }

  return (
    <section className="dashboard-grid">
      <article className="card dashboard-sidebar">
        <h2>{t('dashboardTitle')}</h2>
        {authError && <p className="error">{authError}</p>}
        <p>{t('welcome')}, {verifiedUser?.name || currentUser?.name || t('userFallback')}</p>
        <p>Email: {verifiedUser?.email || currentUser?.email || '-'}</p>
        <p>{t('totalJobs')}: {stats.totalJobs}</p>
        <p>{t('remoteJobs')}: {stats.remoteJobs}</p>
        <p>{t('myApplications')}: {stats.applicationsCount}</p>
        <p>{t('cvUploaded')}: {cvStatus?.has_cv ? t('yes') : t('no')}</p>
        {cvStatus?.cv_filename && <p>{t('cvFile')}: {cvStatus.cv_filename}</p>}

        <h3>{t('myApplications')}</h3>
        <div className="applications-list">
          {applications.length === 0 && <p>{t('noApplications')}</p>}
          {applications.map((item) => (
            <div className="application-item" key={item.id}>
              <strong>{item.job_title}</strong>
              <p>{item.company}</p>
              <small>{t('status')}: {item.status}</small>
            </div>
          ))}
        </div>

        <div className="actions">
          <button
            type="button"
            className={`btn ${searchMethod === 'upload' ? '' : 'btn-secondary'}`}
            onClick={() => setSearchMethod('upload')}
          >
            {t('uploadCv')}
          </button>
          <button
            type="button"
            className={`btn ${searchMethod === 'manual' ? '' : 'btn-secondary'}`}
            onClick={() => setSearchMethod('manual')}
          >
            {t('searchManual')}
          </button>
        </div>

        {searchMethod === 'upload' && (
          <>
            <h3>{t('uploadCv')}</h3>
            <form className="form-grid" onSubmit={handleCvUpload}>
              <input
                type="file"
                accept=".txt,.pdf,.doc,.docx,.xls,.xlsx"
                onChange={(event) => setCvFile(event.target.files?.[0] || null)}
              />
              {uploadError && <p className="error">{uploadError}</p>}
              {uploadMessage && <p className="success">{uploadMessage}</p>}
              <button type="submit" className="btn">
                {t('uploadCvButton')}
              </button>
            </form>
          </>
        )}

        {searchMethod === 'manual' && (
          <>
            <h3>{t('quickSearch')}</h3>
            <form className="form-grid search-form" onSubmit={handleModeSearch}>
              <select
                value=""
                onChange={(event) => {
                  const value = event.target.value
                  if (!value) return
                  setPreferences((prev) => ({ ...prev, job_title: value }))
                  loadDashboardTitleSuggestions(value)
                }}
              >
                <option value="">{t('whatJob')}</option>
                {POPULAR_JOB_OPTIONS.map((option) => (
                  <option key={`dashboard-job-option-${option.value}`} value={option.value}>
                    {getJobLabel(option, lang)}
                  </option>
                ))}
              </select>
              <input
                type="text"
                placeholder={t('whatJob')}
                list="dashboard-job-title-suggestions"
                value={preferences.job_title}
                onChange={(event) => {
                  const value = event.target.value
                  setPreferences((prev) => ({ ...prev, job_title: value }))
                  loadDashboardTitleSuggestions(value)
                }}
              />
              <datalist id="dashboard-job-title-suggestions">
                {dashboardTitleSuggestions.map((title) => (
                  <option key={`dashboard-title-${title}`} value={title} />
                ))}
              </datalist>
              <input type="hidden" value={preferences.country || 'Germany'} />
              <input
                type="text"
                placeholder={t('cityPlaceholder')}
                list="dashboard-city-suggestions"
                value={preferences.city}
                onChange={(event) => {
                  const value = event.target.value
                  setPreferences((prev) => ({ ...prev, city: value }))
                  loadCityOptions('Germany', value)
                }}
              />
              <label>
                {t('radius')}
                <select
                  value={preferences.radius_km}
                  onChange={(event) => setPreferences((prev) => ({ ...prev, radius_km: Number(event.target.value) || 20 }))}
                >
                  <option value={5}>{t('km5')}</option>
                  <option value={10}>{t('km10')}</option>
                  <option value={20}>{t('km20')}</option>
                  <option value={30}>{t('km30')}</option>
                  <option value={50}>{t('km50')}</option>
                  <option value={100}>{t('km100')}</option>
                </select>
              </label>
              <datalist id="dashboard-city-suggestions">
                {cityOptions.map((city) => (
                  <option key={`dashboard-city-${city}`} value={city} />
                ))}
              </datalist>
              {dashboardNearbyCities.length > 0 && (
                <div className="actions">
                  {dashboardNearbyCities.map((nearCity) => (
                    <button
                      key={`dashboard-near-${nearCity}`}
                      type="button"
                      className="btn btn-secondary"
                      onClick={async () => {
                        const nextPreferences = { ...preferences, city: nearCity }
                        setPreferences(nextPreferences)
                        await runDashboardSearch({ append: false, overridePreferences: nextPreferences })
                      }}
                    >
                      {nearCity}
                    </button>
                  ))}
                </div>
              )}
              {(preferences.country || '').trim().toLowerCase() === 'germany' && (preferences.city || '').trim() && (
                <p className="success">{t('nearbyCitiesHint')}</p>
              )}
              {(preferences.country || '').trim() && !(preferences.city || '').trim() && (
                <p className="success">{t('searchAll')} {(preferences.country || '').trim()}</p>
              )}
              <details>
                <summary>{t('advancedFilters')}</summary>
                <div className="form-grid">
                  <select
                    value={preferences.work_mode}
                    onChange={(event) => setPreferences((prev) => ({ ...prev, work_mode: event.target.value }))}
                  >
                    <option value="">{t('workMode')}</option>
                    <option value="remote">{t('remote')}</option>
                    <option value="on-site">{t('onsite')}</option>
                    <option value="hybrid">{t('hybrid')}</option>
                  </select>
                  <select
                    value={preferences.job_type}
                    onChange={(event) => setPreferences((prev) => ({ ...prev, job_type: event.target.value }))}
                  >
                    <option value="">{t('jobType')}</option>
                    <option value="full-time">{t('fullTime')}</option>
                    <option value="part-time">{t('partTime')}</option>
                    <option value="contract">{t('contract')}</option>
                    <option value="internship">{t('internship')}</option>
                  </select>
                  <select
                    value={preferences.experience_level}
                    onChange={(event) => setPreferences((prev) => ({ ...prev, experience_level: event.target.value }))}
                  >
                    <option value="">{t('experienceLevel')}</option>
                    <option value="junior">{t('junior')}</option>
                    <option value="mid">{t('mid')}</option>
                    <option value="senior">{t('senior')}</option>
                  </select>
                </div>
              </details>
              {preferencesError && <p className="error">{preferencesError}</p>}
              <button type="submit" className="btn" disabled={matchesLoading}>
                {matchesLoading ? t('searching') : t('search')}
              </button>
            </form>
            {dashboardCorrectionHint && <p className="success">{dashboardCorrectionHint}</p>}
          </>
        )}
      </article>
      <article className="card chatbot dashboard-results">
        <h2>{t('jobRecommendations')}</h2>
        <h3>{t('aiMatching')}</h3>
        {matchesError && <p className="error">{matchesError}</p>}
        {!matchesError && (
          <p>
            {matches.length > 0
              ? `${t('showingJobs')} ${matches.length} ${t('jobsCountSuffix')}`
              : (matchSearchMeta.message || t('noMatchingJobsBroader'))}
          </p>
        )}
        {!matchesError && !matchesLoading && matches.length === 0 && matchSearchMeta.canBroaden && (
          <div className="job-actions">
            <button type="button" className="btn btn-secondary" onClick={runDashboardBroaderSearch}>
              {t('broadenSearch')}
            </button>
          </div>
        )}
        {!matchesError && !matchesLoading && matches.length === 0 && dashboardAlternativeTitleSuggestion && (
          <div className="job-actions">
            <button type="button" className="btn btn-secondary" onClick={applyDashboardAlternativeTitleSearch}>
              {t('useAlternativeTitle')}: {dashboardAlternativeTitleSuggestion}
            </button>
          </div>
        )}
        <div className="matches-list">
          {matches.length === 0 && !matchesError && !matchSearchMeta.message && <p>{t('noMatches')}</p>}
          {matches.map((item) => (
            <div className="match-item" key={item.job_id}>
              <CompanyLogo job={item} />
              <strong>{item.title}</strong>
              <p>
                {item.company} - {item.city || item.location}
              </p>
              {item.source && <small>{t('source')}: {item.source}</small>}
              {item.work_mode && <small>{item.work_mode}</small>}
              {item.distance_label && <small>{item.distance_label}</small>}
              <small>{formatPostedAgeLabel(item)}</small>
              <small>{t('matchScore')}: {item.score}%</small>
              <p>{getShortReason(item)}</p>
              {isValidApplyUrl(item.apply_url) && !item.is_sample_demo && (
                <p>
                  <a href={item.apply_url} target="_blank" rel="noopener noreferrer">
                  {t('applyEmployer')}
                  </a>
                </p>
              )}
            </div>
          ))}
        </div>
        {matchSearchMeta.hasMore && (
          <div className="job-actions">
            <button
              type="button"
              className="btn"
              onClick={() => runDashboardSearch({ append: true })}
              disabled={matchesLoadingMore}
            >
              {matchesLoadingMore ? t('loadingMore') : t('loadMore')}
            </button>
          </div>
        )}
      </article>
      <article className="card">
        <h2>Career Plan</h2>
        <p>Build a realistic 30/60/90-day plan from your CV and target role.</p>
        {careerPlanError && <p className="error">{careerPlanError}</p>}
        <button type="button" className="btn" onClick={generateCareerPlan} disabled={careerPlanLoading}>
          {careerPlanLoading ? 'Generating...' : 'Generate Career Plan'}
        </button>
        {careerPlan?.plan && (
          <div className="tips-list">
            <div className="tip-item">
              <strong>Focus</strong>
              <p>{careerPlan.plan.summary}</p>
            </div>
            <div className="tip-item">
              <strong>Top Gaps</strong>
              {(careerPlan.plan.gaps || []).map((gap, idx) => <p key={`gap-${idx}`}>- {gap}</p>)}
            </div>
            <div className="tip-item">
              <strong>30 Days</strong>
              {(careerPlan.plan.plan_30 || []).map((step, idx) => <p key={`p30-${idx}`}>- {step}</p>)}
            </div>
            <div className="tip-item">
              <strong>60 Days</strong>
              {(careerPlan.plan.plan_60 || []).map((step, idx) => <p key={`p60-${idx}`}>- {step}</p>)}
            </div>
            <div className="tip-item">
              <strong>90 Days</strong>
              {(careerPlan.plan.plan_90 || []).map((step, idx) => <p key={`p90-${idx}`}>- {step}</p>)}
            </div>
          </div>
        )}
      </article>
    </section>
  )
}

function ChatbotPage({ token, lang, compact = false }) {
  const t = (key) => tFor(lang, key)
  const [messages, setMessages] = useState([
    { role: 'assistant', content: tFor(lang, 'chatbotGreeting') },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [listening, setListening] = useState(false)
  const [micStatus, setMicStatus] = useState('')
  const [interimTranscript, setInterimTranscript] = useState('')
  const [cvFile, setCvFile] = useState(null)
  const [cvText, setCvText] = useState('')
  const [cvSummary, setCvSummary] = useState('')
  const [cvSuggestions, setCvSuggestions] = useState([])
  const [improvedCvText, setImprovedCvText] = useState('')
  const [cvBusy, setCvBusy] = useState(false)
  const [cvStatus, setCvStatus] = useState('')
  const recognitionRef = useRef(null)
  const keepListeningRef = useRef(false)
  const receivedSpeechRef = useRef(false)
  const finalSpeechBufferRef = useRef('')
  const finalizeTimerRef = useRef(null)

  useEffect(() => () => {
    keepListeningRef.current = false
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // noop
      }
    }
    if (finalizeTimerRef.current) {
      clearTimeout(finalizeTimerRef.current)
      finalizeTimerRef.current = null
    }
  }, [])

  useEffect(() => {
    const loadCvGreeting = async () => {
      if (!token) return
      try {
        const response = await fetchWithFallback('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        if (!response.ok) return
        const data = await response.json()
        const name = data?.cv_status?.candidate_name || data?.name || ''
        if (!name) return
        const greetingByLang = {
          en: `Hi ${name}, I found your CV. How can I help you find jobs?`,
          de: `Hallo ${name}, ich habe deinen Lebenslauf gefunden. Wie kann ich dir bei der Jobsuche helfen?`,
          ar: `مرحبًا ${name}، وجدت سيرتك الذاتية. كيف يمكنني مساعدتك في العثور على وظيفة؟`,
        }
        setMessages([{ role: 'assistant', content: greetingByLang[lang] || greetingByLang.en }])
      } catch {
        // keep default greeting
      }
    }
    loadCvGreeting()
  }, [token, lang])

  const sendMessage = async (event) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setError('')
    setLoading(true)
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers.Authorization = `Bearer ${token}`
      const response = await fetchWithFallback('/chatbot/message', {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: text }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Chatbot request failed')
      }
      const replyText = data.reply || 'No response.'
      setMessages((prev) => [...prev, { role: 'assistant', content: replyText }])
    } catch (err) {
      setError(err.message || 'Chatbot failed')
    } finally {
      setLoading(false)
    }
  }

  const stopVoiceInput = () => {
    keepListeningRef.current = false
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // noop
      }
    }
    setListening(false)
    setMicStatus('')
    setInterimTranscript('')
    finalSpeechBufferRef.current = ''
    if (finalizeTimerRef.current) {
      clearTimeout(finalizeTimerRef.current)
      finalizeTimerRef.current = null
    }
  }

  const startVoiceInput = async () => {
    if (typeof window === 'undefined') return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      setMicStatus('Speech recognition is not available in this browser.')
      return
    }
    if (listening) {
      stopVoiceInput()
      return
    }

    try {
      if (navigator?.mediaDevices?.getUserMedia) {
        await navigator.mediaDevices.getUserMedia({ audio: true })
      }
    } catch {
      setMicStatus('Microphone permission denied')
      return
    }

    const recog = new SR()
    recognitionRef.current = recog
    keepListeningRef.current = true
    receivedSpeechRef.current = false
    finalSpeechBufferRef.current = ''
    setInterimTranscript('')
    recog.lang = lang === 'de' ? 'de-DE' : lang === 'ar' ? 'ar-SA' : 'en-US'
    recog.continuous = true
    recog.interimResults = true

    recog.onstart = () => {
      setListening(true)
      setMicStatus('Listening...')
    }
    recog.onresult = (evt) => {
      let finalText = ''
      let interimText = ''
      for (let i = evt.resultIndex; i < evt.results.length; i += 1) {
        const item = evt.results[i]
        const text = (item?.[0]?.transcript || '').trim()
        if (!text) continue
        if (item?.isFinal) finalText += `${text} `
        else interimText += `${text} `
      }
      setInterimTranscript(interimText.trim())
      if (finalText.trim()) {
        receivedSpeechRef.current = true
        finalSpeechBufferRef.current = `${finalSpeechBufferRef.current} ${finalText}`.trim()
      }
      if (finalizeTimerRef.current) {
        clearTimeout(finalizeTimerRef.current)
      }
      finalizeTimerRef.current = setTimeout(() => {
        const combined = finalSpeechBufferRef.current.trim()
        if (combined) {
          setInput((prev) => `${prev} ${combined}`.replace(/\s+/g, ' ').trim())
          finalSpeechBufferRef.current = ''
          keepListeningRef.current = false
          setListening(false)
          setMicStatus('')
          setInterimTranscript('')
          try {
            recog.stop()
          } catch {
            // noop
          }
        }
      }, 700)
    }
    recog.onerror = (evt) => {
      const code = evt?.error || ''
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        setMicStatus('Microphone permission denied')
      } else if (code === 'no-speech') {
        setMicStatus('No speech detected')
      } else {
        setMicStatus('Speech recognition error')
      }
      if (finalizeTimerRef.current) {
        clearTimeout(finalizeTimerRef.current)
        finalizeTimerRef.current = null
      }
    }
    recog.onend = () => {
      if (finalizeTimerRef.current) {
        clearTimeout(finalizeTimerRef.current)
        finalizeTimerRef.current = null
      }
      const combined = finalSpeechBufferRef.current.trim()
      if (combined) {
        setInput((prev) => `${prev} ${combined}`.replace(/\s+/g, ' ').trim())
        finalSpeechBufferRef.current = ''
        setInterimTranscript('')
        setListening(false)
        setMicStatus('')
        return
      }
      if (keepListeningRef.current && !receivedSpeechRef.current) {
        setMicStatus('Listening...')
        try {
          recog.start()
          return
        } catch {
          // fallback to stopped state
        }
      } else if (!receivedSpeechRef.current && keepListeningRef.current === false) {
        setMicStatus('No speech detected')
      } else {
        setMicStatus('')
      }
      setListening(false)
    }
    try {
      recog.start()
    } catch {
      setListening(false)
      setMicStatus('Could not start microphone')
    }
  }

  const analyzeCvInChatbot = async (event) => {
    event.preventDefault()
    if (!cvFile) return
    setCvBusy(true)
    setCvStatus('')
    try {
      const formData = new FormData()
      formData.append('file', cvFile)
      formData.append('language', lang)
      const response = await fetchWithFallback('/chatbot/cv/analyze', { method: 'POST', body: formData })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'CV analyze failed')
      setCvText(data.cv_text || '')
      setCvSummary(data.summary || '')
      setCvSuggestions(Array.isArray(data.suggestions) ? data.suggestions : [])
      setImprovedCvText(data.improved_cv_text || '')
      setCvStatus('CV analyzed successfully.')
    } catch (err) {
      setCvStatus(err.message || 'CV analyze failed')
    } finally {
      setCvBusy(false)
    }
  }

  const regenerateImprovedCv = async () => {
    if (!cvText.trim()) return
    setCvBusy(true)
    setCvStatus('')
    try {
      const response = await fetchWithFallback('/chatbot/cv/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cv_text: cvText,
          language: lang,
          request: input || 'Please generate an improved professional CV.',
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'CV generation failed')
      setCvSummary(data.summary || cvSummary)
      setCvSuggestions(Array.isArray(data.suggestions) ? data.suggestions : cvSuggestions)
      setImprovedCvText(data.improved_cv_text || improvedCvText)
      setCvStatus('Improved CV generated.')
    } catch (err) {
      setCvStatus(err.message || 'CV generation failed')
    } finally {
      setCvBusy(false)
    }
  }

  const saveImprovedCvToProfile = async () => {
    if (!token || !improvedCvText.trim()) return
    const ok = window.confirm('This will overwrite your profile CV with the improved version. Continue?')
    if (!ok) return
    setCvBusy(true)
    setCvStatus('')
    try {
      const response = await fetchWithFallback('/profile/cv/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ cv_text: improvedCvText, filename: 'improved_cv.txt' }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Save failed')
      setCvStatus(data.message || 'Saved.')
    } catch (err) {
      setCvStatus(err.message || 'Save failed')
    } finally {
      setCvBusy(false)
    }
  }

  const copyImprovedCv = async () => {
    if (!improvedCvText.trim()) return
    try {
      await navigator.clipboard.writeText(improvedCvText)
      setCvStatus('Improved CV copied.')
    } catch {
      setCvStatus('Could not copy automatically.')
    }
  }

  const downloadImprovedCv = () => {
    if (!improvedCvText.trim()) return
    const blob = new Blob([improvedCvText], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'improved_cv.txt'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className={`card chatbot ${compact ? 'compact' : ''}`}>
      <h2>{t('chatbot')}</h2>
      {error && <p className="error">{error}</p>}
      <div className="chat-stream">
        {messages.map((message, idx) => (
          <div key={`chat-msg-${idx}`} className={`bubble ${message.role === 'user' ? 'user' : 'bot'}`}>
            {message.content}
          </div>
        ))}
      </div>
      <details>
        <summary>CV tools</summary>
        <form className="form-grid" onSubmit={analyzeCvInChatbot}>
          <input type="file" accept=".txt,.pdf,.doc,.docx,.xls,.xlsx" onChange={(e) => setCvFile(e.target.files?.[0] || null)} />
          <button type="submit" className="btn btn-secondary" disabled={cvBusy || !cvFile}>
            {cvBusy ? 'Processing...' : 'Upload + Analyze CV'}
          </button>
        </form>
        {cvStatus && <p className="success">{cvStatus}</p>}
        {cvSummary && <p>{cvSummary}</p>}
        {cvSuggestions.length > 0 && (
          <div>
            {cvSuggestions.map((tip, idx) => <p key={`tip-${idx}`}>- {tip}</p>)}
          </div>
        )}
        {cvText && (
          <div className="actions">
            <button type="button" className="btn btn-secondary" onClick={regenerateImprovedCv} disabled={cvBusy}>
              Generate improved CV ({lang.toUpperCase()})
            </button>
          </div>
        )}
        {improvedCvText && (
          <div className="form-grid">
            <textarea rows={compact ? 8 : 12} value={improvedCvText} onChange={(e) => setImprovedCvText(e.target.value)} />
            <div className="actions">
              <button type="button" className="btn btn-secondary" onClick={copyImprovedCv}>Copy</button>
              <button type="button" className="btn btn-secondary" onClick={downloadImprovedCv}>Download</button>
              {token && <button type="button" className="btn" onClick={saveImprovedCvToProfile}>Save to profile CV</button>}
            </div>
          </div>
        )}
      </details>
      <form className="chat-input" onSubmit={sendMessage}>
        <input
          type="text"
          placeholder="Ask anything..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button
          type="button"
          className={`icon-btn mic-btn ${listening ? 'active' : ''}`}
          onClick={startVoiceInput}
          aria-label={listening ? 'Stop listening' : 'Speak'}
          title={listening ? 'Stop listening' : 'Speak'}
        >
          <span aria-hidden="true">🎤</span>
        </button>
        <button type="submit" className="btn" disabled={loading}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>
      {listening && interimTranscript && <p className="muted">… {interimTranscript}</p>}
      {micStatus && <p className={micStatus.toLowerCase().includes('denied') ? 'error' : 'success'}>{micStatus}</p>}
    </section>
  )
}

function SettingsPage({ token }) {
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [resetEmail, setResetEmail] = useState('')
  const [resetInfo, setResetInfo] = useState('')
  const [emailVerified, setEmailVerified] = useState(false)
  const [emailNotificationsEnabled, setEmailNotificationsEnabled] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        const response = await fetchWithFallback('/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        if (!response.ok) return
        const data = await response.json()
        setEmail(data.email || '')
        setPhone(data.phone || '')
        setResetEmail(data.email || '')
        setEmailVerified(Boolean(data.email_verified))
        setEmailNotificationsEnabled(Boolean(data.email_notifications_enabled))
      } catch {
        // noop
      }
    }
    load()
  }, [token])

  useEffect(() => {
    const verifyToken = (params.get('verify_email_token') || '').trim()
    if (!verifyToken || !token) return
    const confirm = async () => {
      try {
        const response = await fetchWithFallback(`/auth/email-verification/confirm?token=${encodeURIComponent(verifyToken)}`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
        const data = await response.json()
        if (!response.ok) throw new Error(data.detail || 'Verification failed')
        setStatus(data.message || 'Email verified.')
        setEmailVerified(true)
      } catch (err) {
        setError(err.message || 'Verification failed')
      }
    }
    confirm()
  }, [params, token])

  const saveSettings = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')
    try {
      const response = await fetchWithFallback('/profile/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email, phone }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not save settings')
      setStatus(data.message || 'Settings saved.')
    } catch (err) {
      setError(err.message || 'Could not save settings')
    }
  }

  const requestReset = async (event) => {
    event.preventDefault()
    setResetInfo('')
    try {
      const response = await fetchWithFallback('/auth/password-reset/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: resetEmail }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Reset request failed')
      setResetInfo(data.dev_reset_link ? `${data.message} ${data.dev_reset_link}` : (data.message || 'Reset requested'))
    } catch (err) {
      setResetInfo(err.message || 'Reset request failed')
    }
  }

  const requestEmailVerification = async () => {
    setStatus('')
    setError('')
    try {
      const response = await fetchWithFallback('/auth/email-verification/request', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not request verification')
      setStatus(data.dev_verify_link ? `${data.message} ${data.dev_verify_link}` : (data.message || 'Verification requested'))
    } catch (err) {
      setError(err.message || 'Could not request verification')
    }
  }

  const toggleEmailNotifications = async (enabled) => {
    setStatus('')
    setError('')
    try {
      const response = await fetchWithFallback(`/profile/email-notifications?enabled=${enabled ? 'true' : 'false'}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Could not update notifications')
      setEmailNotificationsEnabled(Boolean(data.enabled))
      setStatus(data.message || 'Updated')
    } catch (err) {
      setError(err.message || 'Could not update notifications')
    }
  }

  return (
    <section className="card">
      <h2>Settings</h2>
      <form className="form-grid" onSubmit={saveSettings}>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
        <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Phone number (optional)" />
        {error && <p className="error">{error}</p>}
        {status && <p className="success">{status}</p>}
        <button className="btn" type="submit">Save profile</button>
      </form>
      <hr />
      <h3>Email verification + notifications</h3>
      <p>{emailVerified ? 'Email verified' : 'Email not verified yet'}</p>
      {!emailVerified && (
        <button type="button" className="btn btn-secondary" onClick={requestEmailVerification}>Send verification email</button>
      )}
      <div className="actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => toggleEmailNotifications(!emailNotificationsEnabled)}
          disabled={!emailVerified}
        >
          {emailNotificationsEnabled ? 'Disable email notifications' : 'Enable email notifications'}
        </button>
      </div>
      <hr />
      <h3>Password reset by email</h3>
      <form className="form-grid" onSubmit={requestReset}>
        <input type="email" value={resetEmail} onChange={(e) => setResetEmail(e.target.value)} placeholder="Account email" />
        <button className="btn btn-secondary" type="submit">Send reset link</button>
      </form>
      {resetInfo && <p className="success">{resetInfo}</p>}
      <p className="muted">SMS reset is optional for future setup and can be enabled when an SMS provider is configured.</p>
    </section>
  )
}

function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = (params.get('token') || '').trim()
  const [newPassword, setNewPassword] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setStatus('')
    try {
      const response = await fetchWithFallback('/auth/password-reset/confirm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Password reset failed')
      setStatus(data.message || 'Password reset successful.')
    } catch (err) {
      setError(err.message || 'Password reset failed')
    }
  }

  return (
    <section className="card">
      <h2>Reset Password</h2>
      {!token && <p className="error">Missing reset token.</p>}
      <form className="form-grid" onSubmit={submit}>
        <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="New password" />
        {error && <p className="error">{error}</p>}
        {status && <p className="success">{status}</p>}
        <button className="btn" type="submit" disabled={!token}>Update password</button>
      </form>
    </section>
  )
}

// eslint-disable-next-line no-unused-vars
function ProtectedRoute({ isAuthenticated, children }) {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
  const [lang, setLang] = useState(() => localStorage.getItem('ui_lang') || 'en')
  const [token, setToken] = useState(() => localStorage.getItem('auth_token') || '')
  // eslint-disable-next-line no-unused-vars
  const [currentUser, setCurrentUser] = useState(() => {
    const raw = localStorage.getItem('auth_user')
    return raw ? JSON.parse(raw) : null
  })

  const isAuthenticated = Boolean(token)

  useEffect(() => {
    localStorage.setItem('ui_lang', lang)
    document.documentElement.lang = lang
    document.documentElement.dir = RTL_LANGS.has(lang) ? 'rtl' : 'ltr'
  }, [lang])

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
        await fetchWithFallback('/auth/logout', {
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

  // eslint-disable-next-line no-unused-vars
  const handleAuthInvalid = () => {
    handleLogout()
  }

  return (
    <BrowserRouter>
      <Layout isAuthenticated={isAuthenticated} onLogout={handleLogout} lang={lang} onLangChange={setLang}>
        <Routes>
          <Route path="/" element={<HomePage lang={lang} />} />
          <Route path="/login" element={<LoginPage onLogin={handleLogin} lang={lang} />} />
          <Route path="/register" element={<RegisterPage lang={lang} />} />
          <Route path="/jobs" element={<JobsPage token={token} lang={lang} />} />
          <Route
            path="/settings"
            element={(
              <ProtectedRoute isAuthenticated={isAuthenticated}>
                <SettingsPage token={token} />
              </ProtectedRoute>
            )}
          />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route
            path="/dashboard"
            element={(
              <ProtectedRoute isAuthenticated={isAuthenticated}>
                <DashboardPage currentUser={currentUser} token={token} onAuthInvalid={handleAuthInvalid} lang={lang} />
              </ProtectedRoute>
            )}
          />
          <Route path="/chatbot" element={<ChatbotPage token={token} lang={lang} />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

export default App
