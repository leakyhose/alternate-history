import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Rome from './pages/Rome'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/rome" element={<Rome />} />
      </Routes>
    </BrowserRouter>
  )
}
