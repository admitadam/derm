# AI Literature Review Pipeline

A full-stack application that helps researchers streamline their literature review process using AI assistance. The application can generate research questions, create PubMed search strings, and automatically find and download available research papers.

## Features

- AI-powered abstract generation based on research questions
- Automated PubMed search string generation
- PubMed paper search and metadata extraction
- Automatic paper availability checking through multiple sources:
  - Unpaywall
  - LibKey Nomad
  - Publisher sites
  - Sci-Hub
- Bulk paper download functionality
- Modern, responsive UI built with Next.js and Tailwind CSS

## Project Structure

```
.
├── frontend/          # Next.js frontend application
│   ├── src/          # React components and pages
│   └── public/       # Static assets
└── backend/          # Python Flask backend
    ├── app.py        # Main application file
    └── requirements.txt  # Python dependencies
```

## Setup

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Backend (Flask)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The backend API will be available at `http://localhost:5000`

## Environment Variables

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:5000
```

### Backend (.env)
```
OPENAI_API_KEY=your_api_key_here
```

## Deployment

- Frontend is deployed to GitHub Pages
- Backend needs to be deployed to a server that can run Python/Flask

## Usage

1. Enter your research question in the input field
2. Click "Generate Abstract" to get an AI-generated literature review abstract
3. Use the generated search string or modify it as needed
4. Click "Search PubMed" to find relevant papers
5. Click "Find Available PDFs" to check paper availability
6. Download available papers individually or in bulk

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.
