import { Link } from 'react-router-dom'

export default function Home() {
  return (
    <div>
      <h1>Home Page</h1>
      <div className='flex'>
        <Link to="/rome" className="">Go to Rome</Link>
    </div>
      
    </div>
  )
}
