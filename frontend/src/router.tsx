import { createBrowserRouter } from 'react-router-dom'
import { ContestDetail } from './pages/ContestDetail'
import { ContestList } from './pages/ContestList'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
import { ProblemDetail } from './pages/ProblemDetail'
import { ProblemList } from './pages/ProblemList'
import { Register } from './pages/Register'
import { SubmissionDetailPage } from './pages/SubmissionDetail'
import { SubmissionList } from './pages/SubmissionList'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { Layout } from './components/Layout'

function protectedLayout(element: React.ReactNode) {
  return (
    <ProtectedRoute>
      <Layout>{element}</Layout>
    </ProtectedRoute>
  )
}

export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
  { path: '/', element: protectedLayout(<Home />) },
  { path: '/problems', element: protectedLayout(<ProblemList />) },
  { path: '/problems/:slug', element: protectedLayout(<ProblemDetail />) },
  { path: '/submissions', element: protectedLayout(<SubmissionList />) },
  { path: '/submissions/:id', element: protectedLayout(<SubmissionDetailPage />) },
  { path: '/contests', element: protectedLayout(<ContestList />) },
  { path: '/contests/:slug', element: protectedLayout(<ContestDetail />) },
])
