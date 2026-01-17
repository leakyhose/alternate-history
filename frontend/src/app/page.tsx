import Link from 'next/link'

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center">
      <h1>Home Page</h1>
      <div className="flex mt-4">
        <Link href="/rome" className="text-amber-400 hover:text-amber-300 text-2xl">
          Go to Rome
        </Link>
      </div>
    </div>
  )
}
