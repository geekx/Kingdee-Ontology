import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import App from './App.tsx'
import './index.css'
import { Chat } from './pages/Chat.tsx'
import { Dashboard } from './pages/Dashboard.tsx'
import { Ontology } from './pages/Ontology.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Dashboard />} />
          <Route path="chat" element={<Chat />} />
          <Route path="ontology" element={<Ontology />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
