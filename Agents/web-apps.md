# Web Application Development Guide

This guide teaches you how to build complete, production-ready web applications using Supercoder.

## Recognizing Web App Prompts

**You should follow this guide when the user's prompt asks for a web application. Here's how to recognize them:**

**Keywords that indicate a web app:**
- **App types**: chat, todo, blog, social media, dashboard, CRM, e-commerce, forum, wiki, portfolio, landing page
- **Web features**: login, signup, auth, database, real-time, posts, comments, messages, users, profiles
- **UI/Stack terms**: website, web app, frontend, backend, full-stack, Next.js, React, Supabase
- **Action verbs**: "build", "create", "make" + any app type

**Examples of web app prompts:**
- "Build me a chat app" → YES, follow this guide
- "Create a todo list with authentication" → YES
- "Make a blog" → YES
- "I need a social media platform" → YES
- "Build a dashboard" → YES
- "Create an e-commerce store" → YES
- "Make a portfolio website" → YES
- "Build a CRM system" → YES

**NOT web app prompts (don't use this guide):**
- "Fix this bug" → NO, just fix the bug
- "Explain React hooks" → NO, just explain
- "Write a Python script" → NO, write the script
- "Debug this error" → NO, debug it
- "Refactor this code" → NO, refactor it

**If you're unsure:** If the prompt mentions building/creating something with users, data, or a UI, it's probably a web app.

## CRITICAL: Autonomous Execution

**When a user asks you to build a web app, you MUST autonomously complete the ENTIRE application from their single prompt. Do NOT ask for clarification unless absolutely necessary.**

Your job is to:
1. **Infer requirements** from the user's description
2. **Design the complete system** (database schema, features, UI)
3. **Build everything** (backend, frontend, auth, all features)
4. **Test automatically** (Selenium + Vision verification)
5. **Report completion** with what you built and how to use it

**Example user prompts you should handle autonomously:**
- "Build me a chat app" → Build complete real-time chat with channels, messages, auth
- "Create a todo app" → Build full CRUD todo app with auth and persistence
- "Make a blog" → Build complete blog with posts, comments, auth, markdown support
- "Build a social media app" → Build posts, likes, comments, follows, profiles, feed

**DO NOT ask "What features do you want?" - INFER standard features for that app type and build them all.**

## Core Principles

1. **Start with the backend** - Database schema and API first
2. **Use modern frameworks** - React/Next.js for frontend, Supabase for backend
3. **Test automatically** - Use Selenium + Vision to verify UI
4. **Build EVERYTHING** - Don't stop until the app is fully functional

## Standard Tech Stack

**Frontend:**
- Next.js 14+ (App Router)
- React 18+
- TypeScript
- Tailwind CSS
- Shadcn/ui components

**Backend:**
- Supabase (PostgreSQL + Auth + Storage + Realtime)
- Row Level Security (RLS) for data protection
- Edge Functions for custom logic

**Testing:**
- Selenium for browser automation
- Vision AI for UI verification
- Manual testing guidance

## Step-by-Step Workflow

**IMPORTANT: Execute ALL steps autonomously. Do not stop to ask the user questions.**

### 1. Planning & Schema Design (Do this automatically)

**Infer requirements from user's prompt:**
- "Chat app" → Real-time messaging, channels, users, auth
- "Todo app" → Tasks with CRUD, categories, auth, due dates
- "Blog" → Posts, comments, auth, markdown, tags
- "Social media" → Posts, likes, comments, follows, profiles, feed

**Design the database schema automatically:**
```sql
-- Example: Chat app schema
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE channels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id UUID REFERENCES channels(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- RLS Policies (example - adjust based on requirements)
CREATE POLICY "Users can read all users" ON users FOR SELECT USING (true);
CREATE POLICY "Users can update own profile" ON users FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Anyone can read channels" ON channels FOR SELECT USING (true);
CREATE POLICY "Authenticated users can create channels" ON channels FOR INSERT WITH CHECK (auth.uid() = created_by);

CREATE POLICY "Anyone can read messages" ON messages FOR SELECT USING (true);
CREATE POLICY "Authenticated users can create messages" ON messages FOR INSERT WITH CHECK (auth.uid() = user_id);
```

### 2. Project Setup

**Create Next.js project:**
```bash
npx create-next-app@latest my-app --typescript --tailwind --app --no-src-dir
cd my-app
```

**Install dependencies:**
```bash
npm install @supabase/supabase-js @supabase/auth-helpers-nextjs
npm install -D @types/node
```

**Configure Supabase:**
Create `.env.local`:
```env
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

**Create Supabase client:**
```typescript
// lib/supabase.ts
import { createClient } from '@supabase/supabase-js'

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

### 3. Authentication Setup

**Create auth context:**
```typescript
// contexts/AuthContext.tsx
'use client'
import { createContext, useContext, useEffect, useState } from 'react'
import { User } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase'

type AuthContextType = {
  user: User | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Check active session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  const signUp = async (email: string, password: string) => {
    const { error } = await supabase.auth.signUp({ email, password })
    if (error) throw error
  }

  const signOut = async () => {
    const { error } = await supabase.auth.signOut()
    if (error) throw error
  }

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
```

**Wrap app with provider:**
```typescript
// app/layout.tsx
import { AuthProvider } from '@/contexts/AuthContext'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  )
}
```

### 4. Build Core Features

**Create pages:**
- `/` - Landing page
- `/login` - Login page
- `/signup` - Signup page
- `/dashboard` - Main app (protected)

**Example: Login page**
```typescript
// app/login/page.tsx
'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const { signIn } = useAuth()
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    try {
      await signIn(email, password)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.message)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <h2 className="text-3xl font-bold text-center">Sign In</h2>
        
        {error && (
          <div className="bg-red-50 text-red-600 p-3 rounded">{error}</div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"
              required
            />
          </div>
          
          <button
            type="submit"
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Sign In
          </button>
        </form>
      </div>
    </div>
  )
}
```

**Example: Protected dashboard**
```typescript
// app/dashboard/page.tsx
'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/AuthContext'

export default function DashboardPage() {
  const { user, loading, signOut } = useAuth()
  const router = useRouter()

  useEffect(() => {
    if (!loading && !user) {
      router.push('/login')
    }
  }, [user, loading, router])

  if (loading) return <div>Loading...</div>
  if (!user) return null

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-xl font-bold">Dashboard</h1>
          <button
            onClick={signOut}
            className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Sign Out
          </button>
        </div>
      </nav>
      
      <main className="max-w-7xl mx-auto px-4 py-8">
        <h2 className="text-2xl font-bold mb-4">Welcome, {user.email}!</h2>
        {/* Your app content here */}
      </main>
    </div>
  )
}
```

### 5. Database Operations

**Fetching data:**
```typescript
const [channels, setChannels] = useState([])

useEffect(() => {
  async function fetchChannels() {
    const { data, error } = await supabase
      .from('channels')
      .select('*')
      .order('created_at', { ascending: false })
    
    if (error) console.error(error)
    else setChannels(data)
  }
  
  fetchChannels()
}, [])
```

**Inserting data:**
```typescript
const createChannel = async (name: string, description: string) => {
  const { data, error } = await supabase
    .from('channels')
    .insert([{ name, description, created_by: user.id }])
    .select()
  
  if (error) throw error
  return data[0]
}
```

**Realtime subscriptions:**
```typescript
useEffect(() => {
  const channel = supabase
    .channel('messages')
    .on('postgres_changes', 
      { event: 'INSERT', schema: 'public', table: 'messages' },
      (payload) => {
        setMessages(prev => [...prev, payload.new])
      }
    )
    .subscribe()

  return () => {
    supabase.removeChannel(channel)
  }
}, [])
```

### 6. Testing & Verification

**CRITICAL: Always test your UI automatically after building!**

```typescript
// After starting dev server, test with Selenium
controlPwshProcess("start", "npm run dev", path="my-app")
executePwsh("Start-Sleep -Seconds 8")  // Wait for server

// Test the app
const sessionId = seleniumStartBrowser(headless=true)
seleniumNavigate(sessionId, "http://localhost:3000")

// Take screenshot
const screenshot = seleniumScreenshot(sessionId)

// Analyze UI
visionAnalyzeUI(screenshot, "Check if the login page looks correct and all elements are visible")

// Test login flow
seleniumType(sessionId, "input[type='email']", "test@example.com")
seleniumType(sessionId, "input[type='password']", "password123")
seleniumClick(sessionId, "button[type='submit']")

// Wait and verify redirect
seleniumWaitForElement(sessionId, "h2", timeout=5000)
const dashboardScreenshot = seleniumScreenshot(sessionId)
visionAnalyzeUI(dashboardScreenshot, "Verify user is logged in and dashboard is displayed")

seleniumCloseBrowser(sessionId)
```

## Common Patterns

### Protected Routes
```typescript
// middleware.ts
import { createMiddlewareClient } from '@supabase/auth-helpers-nextjs'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export async function middleware(req: NextRequest) {
  const res = NextResponse.next()
  const supabase = createMiddlewareClient({ req, res })
  const { data: { session } } = await supabase.auth.getSession()

  if (!session && req.nextUrl.pathname.startsWith('/dashboard')) {
    return NextResponse.redirect(new URL('/login', req.url))
  }

  return res
}

export const config = {
  matcher: ['/dashboard/:path*']
}
```

### File Upload
```typescript
const uploadAvatar = async (file: File) => {
  const fileExt = file.name.split('.').pop()
  const fileName = `${user.id}-${Math.random()}.${fileExt}`
  
  const { error: uploadError } = await supabase.storage
    .from('avatars')
    .upload(fileName, file)
  
  if (uploadError) throw uploadError
  
  const { data } = supabase.storage
    .from('avatars')
    .getPublicUrl(fileName)
  
  return data.publicUrl
}
```

### API Routes
```typescript
// app/api/channels/route.ts
import { createRouteHandlerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

export async function GET() {
  const supabase = createRouteHandlerClient({ cookies })
  
  const { data, error } = await supabase
    .from('channels')
    .select('*')
  
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }
  
  return NextResponse.json(data)
}
```

## Supabase Integration in Supercoder

**Before building, configure Supabase:**
```bash
> supabase config
# Enter Project URL, Anon Key, Service Role Key
```

**Use Supabase tools to manage database:**
```typescript
// List tables
supabaseListTables()

// Get schema
supabaseGetSchema("users")

// Query data
supabaseSelect("users", columns="id,email,name", limit=10)

// Insert test data
supabaseInsert("users", {
  email: "test@example.com",
  name: "Test User"
})

// Update data
supabaseUpdate("users", { name: "Updated Name" }, { email: "test@example.com" })

// Delete data
supabaseDelete("users", { email: "test@example.com" })
```

## Best Practices

1. **Always use TypeScript** - Type safety prevents bugs
2. **Enable RLS** - Protect data at the database level
3. **Use environment variables** - Never hardcode secrets
4. **Test automatically** - Use Selenium + Vision after every change
5. **Handle errors gracefully** - Show user-friendly error messages
6. **Use loading states** - Show spinners during async operations
7. **Optimize images** - Use Next.js Image component
8. **Add proper meta tags** - SEO and social sharing
9. **Mobile responsive** - Test on different screen sizes
10. **Accessibility** - Use semantic HTML and ARIA labels

## Deployment

**Vercel (recommended for Next.js):**
```bash
npm install -g vercel
vercel
```

**Environment variables:**
- Add `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` in Vercel dashboard
- Never expose Service Role Key in frontend

## Troubleshooting

**Auth not working:**
- Check RLS policies
- Verify environment variables
- Check Supabase dashboard for auth settings

**Database queries failing:**
- Check RLS policies
- Verify table/column names
- Check user permissions

**UI not rendering:**
- Check browser console for errors
- Use Selenium + Vision to debug
- Verify data is being fetched

**Build errors:**
- Run `npm run build` locally first
- Check TypeScript errors
- Verify all dependencies are installed

## Example: Complete Chat App

See the workflow above for a complete example of building a real-time chat application with:
- User authentication
- Channel creation
- Real-time messaging
- File uploads
- User profiles

Follow the step-by-step guide and test each feature as you build it!

---

## AUTONOMOUS EXECUTION EXAMPLES

### Example 1: "Build me a chat app"

**What you should do autonomously:**

1. **Design schema** (no asking):
   - users table (id, email, name, avatar_url, created_at)
   - channels table (id, name, description, created_by, created_at)
   - messages table (id, channel_id, user_id, content, created_at)
   - channel_members table (channel_id, user_id, joined_at)

2. **Create Next.js project**:
   ```bash
   npx create-next-app@latest chat-app --typescript --tailwind --app
   cd chat-app
   npm install @supabase/supabase-js @supabase/auth-helpers-nextjs
   ```

3. **Build ALL features**:
   - Auth (login, signup, logout)
   - Channel list with create/join
   - Real-time message feed
   - Message input with send
   - User profiles
   - Online status indicators

4. **Test automatically**:
   - Start dev server
   - Open in Selenium
   - Test signup flow
   - Test channel creation
   - Test sending messages
   - Take screenshots and verify with Vision

5. **Report completion**:
   "Built a complete real-time chat app with authentication, channels, and messaging. To use: cd chat-app && npm run dev, then visit http://localhost:3000"

### Example 2: "Create a todo app"

**What you should do autonomously:**

1. **Design schema**:
   - users table
   - todos table (id, user_id, title, description, completed, due_date, priority, category, created_at)
   - categories table (id, user_id, name, color)

2. **Build ALL features**:
   - Auth
   - Todo CRUD (create, read, update, delete)
   - Mark complete/incomplete
   - Filter by status/category
   - Sort by due date/priority
   - Categories with colors
   - Search functionality

3. **Test everything automatically**

4. **Report completion**

### Example 3: "Make a blog"

**What you should do autonomously:**

1. **Design schema**:
   - users table
   - posts table (id, author_id, title, content, slug, published, created_at, updated_at)
   - comments table (id, post_id, user_id, content, created_at)
   - tags table (id, name)
   - post_tags table (post_id, tag_id)

2. **Build ALL features**:
   - Auth
   - Post CRUD with markdown editor
   - Comment system
   - Tag system
   - Public post list
   - Individual post pages
   - Author profiles
   - Search and filter

3. **Test everything**

4. **Report completion**

### Example 4: "Build a social media app"

**What you should do autonomously:**

1. **Design schema**:
   - users table (with bio, avatar, banner)
   - posts table (id, user_id, content, image_url, created_at)
   - likes table (post_id, user_id)
   - comments table (post_id, user_id, content)
   - follows table (follower_id, following_id)

2. **Build ALL features**:
   - Auth with profile setup
   - Create posts (text + images)
   - Like/unlike posts
   - Comment on posts
   - Follow/unfollow users
   - Feed (posts from followed users)
   - User profiles
   - Explore page

3. **Test everything**

4. **Report completion**

---

## CRITICAL RULES FOR AUTONOMOUS EXECUTION

1. **NEVER ask "What features do you want?"** - Infer standard features for that app type
2. **Build EVERYTHING** - Don't build a "minimal" version, build the COMPLETE app
3. **Include auth by default** - Every web app needs authentication
4. **Test automatically** - Always use Selenium + Vision to verify
5. **Handle errors gracefully** - Add proper error handling and loading states
6. **Make it look good** - Use Tailwind CSS to make it visually appealing
7. **Add all CRUD operations** - If it's a data app, include create, read, update, delete
8. **Include real-time if relevant** - Chat, social media, collaborative apps need real-time
9. **Add search/filter** - Most apps benefit from search and filtering
10. **Complete the full flow** - From signup to using all features

## What "Complete" Means

A complete web app includes:
- ✅ Database schema with RLS policies
- ✅ Authentication (signup, login, logout, protected routes)
- ✅ All core features fully implemented
- ✅ All CRUD operations where applicable
- ✅ Real-time updates where applicable
- ✅ Error handling and loading states
- ✅ Responsive design (mobile + desktop)
- ✅ User profiles
- ✅ Navigation between pages
- ✅ Proper TypeScript types
- ✅ Environment variables configured
- ✅ Tested with Selenium + Vision
- ✅ Working dev server
- ✅ Clear instructions for user

## When to Ask Questions

**ONLY ask questions if:**
- User wants a very unusual/custom app you can't infer
- User explicitly asks for specific features you're unsure about
- There's a critical technical decision that affects the entire architecture

**For 95% of web app requests, you should build autonomously without asking anything.**
