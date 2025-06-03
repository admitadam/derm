import * as React from "react"
import Link from "next/link"

function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-gray-50 border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex-shrink-0">
            <Link href="/" className="flex items-center">
              <span className="text-2xl font-bold text-gray-900">Dermslop</span>
            </Link>
          </div>
          <div className="flex items-center">
            <a 
              href="https://elicit.com" 
              target="_blank" 
              rel="noopener noreferrer" 
              className="bg-black text-white px-4 py-2 rounded-md hover:bg-gray-800 transition-colors font-bold flex items-center"
            >
              Go to Elicit <span className="ml-2">&gt;</span>
            </a>
          </div>
        </div>
      </div>
    </nav>
  )
}

export { Navbar } 