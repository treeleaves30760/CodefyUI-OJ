import { createBrowserRouter } from 'react-router-dom'
import { ContestDetail } from './pages/ContestDetail'
import { ContestList } from './pages/ContestList'
import { Home } from './pages/Home'
import { Login } from './pages/Login'
import { ProblemDetail } from './pages/ProblemDetail'
import { ProblemList } from './pages/ProblemList'
import { Register } from './pages/Register'
import { Setup } from './pages/Setup'
import { SubmissionDetailPage } from './pages/SubmissionDetail'
import { SubmissionList } from './pages/SubmissionList'
import { AdminLayout } from './pages/admin/AdminLayout'
import { AdminDashboard } from './pages/admin/Dashboard'
import { AdminProblems } from './pages/admin/Problems'
import { AdminContests } from './pages/admin/Contests'
import { AdminUsers } from './pages/admin/Users'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AdminRoute } from './auth/AdminRoute'
import { Layout } from './components/Layout'

function protectedLayout(element: React.ReactNode) {
  return (
    <ProtectedRoute>
      <Layout>{element}</Layout>
    </ProtectedRoute>
  )
}

function publicLayout(element: React.ReactNode) {
  return <Layout>{element}</Layout>
}

export const router = createBrowserRouter([
  { path: '/setup', element: <Setup /> },
  { path: '/login', element: <Login /> },
  { path: '/register', element: <Register /> },
  { path: '/', element: protectedLayout(<Home />) },
  { path: '/problems', element: publicLayout(<ProblemList />) },
  { path: '/problems/:slug', element: publicLayout(<ProblemDetail />) },
  { path: '/submissions', element: protectedLayout(<SubmissionList />) },
  { path: '/submissions/:id', element: protectedLayout(<SubmissionDetailPage />) },
  { path: '/contests', element: protectedLayout(<ContestList />) },
  { path: '/contests/:slug', element: protectedLayout(<ContestDetail />) },
  {
    path: '/admin',
    element: (
      <ProtectedRoute>
        <AdminRoute>
          <AdminLayout />
        </AdminRoute>
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <AdminDashboard /> },
      { path: 'problems', element: <AdminProblems /> },
      { path: 'contests', element: <AdminContests /> },
      { path: 'users', element: <AdminUsers /> },
    ],
  },
])
