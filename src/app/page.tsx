"use client";

import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { Navbar } from "@/components/ui/navbar";

interface ErrorState {
  message: string;
  type: 'generate' | 'search' | 'download';
}

interface PaperInfo {
  title: string;
  authors: string;
  year: string;
  journal: string;
  doi: string | null;
  pmid?: string;
  pubmed_url?: string;
  abstract: string;
  access_urls: {
    libkey: string | null;
    doi: string | null;
    unpaywall: string | null;
    scihub: string | null;
  };
  availability: {
    is_available: boolean;
    is_findable: boolean;
    sources: string[];
  };
}

interface DownloadInfo {
  title: string;
  urls: {
    libkey: string | null | undefined;
    doi: string | null | undefined;
    unpaywall: string | null | undefined;
    scihub: string | null | undefined;
  };
}

interface GeneratedAbstract {
  content: string;
  visible: boolean;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [searchString, setSearchString] = useState("");
  const [resultCount, setResultCount] = useState<number | null>(null);
  const [pdfs, setPdfs] = useState<PaperInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  const [page, setPage] = useState(1);
  const [generatedAbstract, setGeneratedAbstract] = useState<GeneratedAbstract>({ content: "", visible: false });
  const itemsPerPage = 50;

  // Configure your backend API URL here
  const API_URL = "http://localhost:5000";

  const validateQuestion = (q: string) => {
    if (q.length < 10) return "Question must be at least 10 characters long";
    if (!q.includes("?")) return "Question should end with a question mark";
    return null;
  };

  const handleGenerateAbstract = async () => {
    const validationError = validateQuestion(question);
    if (validationError) {
      setError({ message: validationError, type: 'generate' });
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const abstractRes = await fetch(`${API_URL}/generate-abstract`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        },
        body: JSON.stringify({ question })
      });
      if (!abstractRes.ok) throw new Error("Failed to generate abstract");
      const abstractData = await abstractRes.json();
      setGeneratedAbstract({ content: abstractData.abstract, visible: true });
    } catch (error) {
      setError({ 
        message: error instanceof Error ? error.message : "Failed to generate abstract", 
        type: 'generate' 
      });
    }
    setLoading(false);
  };

  const handleGenerateSearch = async () => {
    setLoading(true);
    setError(null);
    try {
      const searchRes = await fetch(`${API_URL}/generate-search-string`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        },
        body: JSON.stringify({ question })
      });
      if (!searchRes.ok) throw new Error("Failed to generate search string");
      const searchData = await searchRes.json();
      setSearchString(searchData.search_string);
    } catch (error) {
      setError({ 
        message: error instanceof Error ? error.message : "Failed to generate search string", 
        type: 'generate' 
      });
    }
    setLoading(false);
  };

  const handlePubMedSearch = async () => {
    if (!searchString.trim()) {
      setError({ message: "Search string cannot be empty", type: 'search' });
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/pubmed-search`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        },
        body: JSON.stringify({ search_string: searchString })
      });
      if (!res.ok) throw new Error("Failed to search PubMed");
      const data = await res.json();
      setResultCount(data.result_count);
    } catch (error) {
      setError({ 
        message: error instanceof Error ? error.message : "Failed to search PubMed", 
        type: 'search' 
      });
    }
    setLoading(false);
  };

  const handleDownloadPDFs = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/download-pdfs`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        },
        body: JSON.stringify({ search_string: searchString })
      });
      if (!res.ok) throw new Error("Failed to find PDFs");
      const data = await res.json();
      setPdfs(data.pdfs);
      setPage(1);
    } catch (error) {
      setError({ 
        message: error instanceof Error ? error.message : "Failed to find PDFs", 
        type: 'download' 
      });
    }
    setLoading(false);
  };

  const handleExport = () => {
    const data = {
      question,
      searchString,
      resultCount,
      pdfs: pdfs.map(pdf => ({
        title: pdf.title,
        urls: pdf.access_urls
      }))
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'research-results.json';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  const totalPages = Math.ceil(pdfs.length / itemsPerPage);

  return (
    <>
      <Navbar />
      <main className="min-h-screen pt-20 pb-32 bg-gray-50">
        <div className="max-w-4xl mx-auto space-y-8 px-4">
          <h1 className="text-4xl font-bold text-center mb-8 mt-16">AI Literature Review Pipeline</h1>
          
          <Card className="overflow-hidden">
            <CardContent className="p-0">
              <div className="border-b">
                <h3 className="px-4 pt-1.5 pb-1.5 text-base font-bold tracking-wide">Research Question</h3>
              </div>
              <div className="px-4 py-3 space-y-3">
                <Input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Enter your research question... (end with a question mark)"
                  className="w-full"
                />
                {error?.type === 'generate' && (
                  <p className="text-sm text-red-500">{error.message}</p>
                )}
                <Button 
                  onClick={handleGenerateAbstract}
                  disabled={!question || loading}
                  className="w-full"
                >
                  {loading ? <Spinner className="mr-2" /> : null}
                  Generate Abstract
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Generated Abstract Card */}
          {generatedAbstract.visible && (
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <div className="border-b">
                  <h3 className="px-4 pt-1.5 pb-1.5 text-base font-bold tracking-wide">Generated Literature Review Abstract</h3>
                </div>
                <div className="px-4 py-3">
                  <div className="space-y-2">
                    {generatedAbstract.content.split('\n').map((paragraph, index) => {
                      if (paragraph.includes('**')) {
                        const sectionTitle = paragraph.replace(/\*\*/g, '');
                        return (
                          <div key={index}>
                            <h3 className="text-sm font-bold tracking-wide">
                              {sectionTitle}
                            </h3>
                          </div>
                        );
                      }
                      return (
                        <p key={index} className="text-sm leading-relaxed">
                          {paragraph}
                        </p>
                      );
                    })}
                  </div>
                  <div className="mt-4">
                    <Button 
                      onClick={handleGenerateSearch}
                      disabled={loading}
                      className="w-full"
                    >
                      {loading ? <Spinner className="mr-2" /> : null}
                      Generate Search String
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {searchString && (
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <div className="border-b">
                  <h3 className="px-4 pt-1.5 pb-1.5 text-base font-bold tracking-wide">Generated PubMed Search String</h3>
                </div>
                <div className="px-4 py-3 space-y-3">
                  <Textarea
                    value={searchString}
                    onChange={(e) => setSearchString(e.target.value)}
                    className="font-mono text-sm"
                    rows={3}
                  />
                  {error?.type === 'search' && (
                    <p className="text-sm text-red-500">{error.message}</p>
                  )}
                  <Button 
                    onClick={handlePubMedSearch}
                    disabled={loading}
                    className="w-full"
                  >
                    {loading ? <Spinner className="mr-2" /> : null}
                    Search PubMed
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {resultCount !== null && (
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <div className="border-b">
                  <h3 className="px-4 pt-1.5 pb-1.5 text-base font-bold tracking-wide">Search Results</h3>
                </div>
                <div className="px-4 py-3 space-y-3">
                  <h4 className={`text-base font-bold tracking-wide ${resultCount > 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {resultCount} papers found
                  </h4>
                  <Button 
                    onClick={handleDownloadPDFs}
                    disabled={loading}
                    className="w-full"
                  >
                    {loading ? <Spinner className="mr-2" /> : null}
                    Find Available PDFs
                  </Button>
                  {error?.type === 'download' && (
                    <p className="text-sm text-red-500">{error.message}</p>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {pdfs.length > 0 && (
            <Card className="overflow-hidden">
              <CardContent className="p-0">
                <div className="border-b">
                  <div className="px-4 pt-1.5 pb-1.5 flex items-center justify-between">
                    <h3 className="text-base font-bold tracking-wide">Papers Found ({pdfs.length})</h3>
                    <Button
                      onClick={async () => {
                        try {
                          setLoading(true);
                          const availablePapers = pdfs.filter(p => p.availability.is_available);
                          if (availablePapers.length === 0) {
                            setError({
                              message: "No papers available for direct download",
                              type: 'download'
                            });
                            setLoading(false);
                            return;
                          }
                          
                          const res = await fetch("http://localhost:5000/bulk-download", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ papers: availablePapers })
                          });
                          
                          if (!res.ok) {
                            throw new Error("Failed to prepare bulk download");
                          }
                          
                          const blob = await res.blob();
                          const url = window.URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = 'papers.zip';
                          document.body.appendChild(a);
                          a.click();
                          
                          window.URL.revokeObjectURL(url);
                          document.body.removeChild(a);
                          setLoading(false);
                        } catch (error) {
                          setLoading(false);
                          setError({
                            message: error instanceof Error ? error.message : "Failed to prepare bulk download",
                            type: 'download'
                          });
                        }
                      }}
                      disabled={!pdfs.some(p => p.availability.is_available)}
                      className="bg-black text-white hover:bg-gray-800"
                    >
                      {loading ? <Spinner className="mr-2" /> : null}
                      Download Available ({pdfs.filter(p => p.availability.is_available).length})
                    </Button>
                  </div>
                </div>

                <div className="divide-y">
                  <div className="px-4 py-3">
                    <h3 className="text-lg font-semibold text-green-600 mb-1 flex items-center">
                      <span>Directly Downloadable Papers ({pdfs.filter(p => p.availability.is_available).length})</span>
                      <span className="ml-2 text-sm font-normal text-gray-600">
                        Available through Unpaywall or direct PDF links
                      </span>
                    </h3>
                    <div className="space-y-3">
                      {pdfs
                        .filter(p => p.availability.is_available)
                        .slice((page - 1) * itemsPerPage, page * itemsPerPage)
                        .map((pdf, index) => (
                          <div key={index} className="p-3 bg-white border-2 border-green-200 rounded-md hover:border-green-300 transition-colors">
                            <div className="flex items-start justify-between">
                              <div className="flex-1 mr-4">
                                <h4 className="font-medium text-lg mb-1">{pdf.title}</h4>
                                <p className="text-sm text-gray-600 mb-1">{pdf.authors}</p>
                                <p className="text-sm text-gray-600 mb-2">
                                  {pdf.journal} • {pdf.year}
                                </p>
                                <div className="space-x-2">
                                  {pdf.pubmed_url && (
                                    <a
                                      href={pdf.pubmed_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center px-3 py-1 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700"
                                    >
                                      PubMed
                                    </a>
                                  )}
                                  
                                  {pdf.doi && (
                                    <>
                                      <a
                                        href={pdf.access_urls.libkey || undefined}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center px-3 py-1 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700"
                                      >
                                        LibKey Nomad
                                      </a>
                                      <a
                                        href={pdf.access_urls.doi || undefined}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center px-3 py-1 bg-gray-600 text-white text-sm rounded-md hover:bg-gray-700"
                                      >
                                        Publisher Site
                                      </a>
                                    </>
                                  )}
                                  
                                  {pdf.access_urls.unpaywall && (
                                    <a
                                      href={pdf.access_urls.unpaywall}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center px-3 py-1 bg-green-600 text-white text-sm rounded-md hover:bg-green-700"
                                    >
                                      Unpaywall PDF
                                    </a>
                                  )}
                                  
                                  {pdf.doi && (
                                    <a
                                      href={pdf.access_urls.scihub || undefined}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center px-3 py-1 bg-red-600 text-white text-sm rounded-md hover:bg-red-700"
                                    >
                                      Sci-Hub
                                    </a>
                                  )}
                                </div>
                                <div className="mt-2">
                                  <button
                                    onClick={() => {
                                      const elem = document.getElementById(`abstract-${index}`);
                                      if (elem) {
                                        elem.style.display = elem.style.display === 'none' ? 'block' : 'none';
                                      }
                                    }}
                                    className="text-sm text-blue-600 hover:text-blue-800"
                                  >
                                    Show/Hide Abstract
                                  </button>
                                  <p
                                    id={`abstract-${index}`}
                                    className="mt-2 text-sm text-gray-600"
                                    style={{ display: 'none' }}
                                  >
                                    {pdf.abstract}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>

                  <div className="px-4 py-3">
                    <h3 className="text-lg font-semibold text-blue-600 mb-1 flex items-center">
                      <span>Findable Papers ({pdfs.filter(p => p.availability.is_findable && !p.availability.is_available).length})</span>
                      <span className="ml-2 text-sm font-normal text-gray-600">
                        Has DOI but requires institutional access or manual download
                      </span>
                    </h3>
                    <div className="space-y-3">
                      {pdfs
                        .filter(p => p.availability.is_findable && !p.availability.is_available)
                        .slice((page - 1) * itemsPerPage, page * itemsPerPage)
                        .map((pdf, index) => (
                          <div key={index} className="p-3 bg-white border-2 border-blue-200 rounded-md hover:border-blue-300 transition-colors">
                            <div className="flex items-start justify-between">
                              <div className="flex-1 mr-4">
                                <h4 className="font-medium text-lg mb-1">{pdf.title}</h4>
                                <p className="text-sm text-gray-600 mb-1">{pdf.authors}</p>
                                <p className="text-sm text-gray-600 mb-2">
                                  {pdf.journal} • {pdf.year}
                                </p>
                                <div className="space-x-2">
                                  {pdf.pubmed_url && (
                                    <a
                                      href={pdf.pubmed_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center px-3 py-1 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700"
                                    >
                                      PubMed
                                    </a>
                                  )}
                                  
                                  {pdf.doi ? (
                                    <>
                                      <a
                                        href={pdf.access_urls.doi || undefined}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center px-3 py-1 bg-gray-600 text-white text-sm rounded-md hover:bg-gray-700"
                                      >
                                        Publisher Site
                                      </a>
                                      <a
                                        href={pdf.access_urls.scihub || undefined}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center px-3 py-1 bg-red-600 text-white text-sm rounded-md hover:bg-red-700"
                                      >
                                        Try Sci-Hub
                                      </a>
                                    </>
                                  ) : (
                                    <span className="inline-flex items-center px-3 py-1 bg-gray-200 text-gray-700 text-sm rounded-md">
                                      No DOI Available
                                    </span>
                                  )}
                                </div>
                                <div className="mt-2">
                                  <button
                                    onClick={() => {
                                      const elem = document.getElementById(`abstract-${index}`);
                                      if (elem) {
                                        elem.style.display = elem.style.display === 'none' ? 'block' : 'none';
                                      }
                                    }}
                                    className="text-sm text-blue-600 hover:text-blue-800"
                                  >
                                    Show/Hide Abstract
                                  </button>
                                  <p
                                    id={`abstract-${index}`}
                                    className="mt-2 text-sm text-gray-600"
                                    style={{ display: 'none' }}
                                  >
                                    {pdf.abstract}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>

                  <div className="px-4 py-3">
                    <h3 className="text-lg font-semibold text-gray-600 mb-1 flex items-center">
                      <span>Unavailable Papers ({pdfs.filter(p => !p.availability.is_findable).length})</span>
                      <span className="ml-2 text-sm font-normal text-gray-600">
                        No DOI or access links available
                      </span>
                    </h3>
                    <div className="space-y-3">
                      {pdfs
                        .filter(p => !p.availability.is_findable)
                        .slice((page - 1) * itemsPerPage, page * itemsPerPage)
                        .map((pdf, index) => (
                          <div key={index} className="p-3 bg-white border border-gray-200 rounded-md hover:border-gray-300 transition-colors opacity-75">
                            <div className="flex items-start justify-between">
                              <div className="flex-1 mr-4">
                                <h4 className="font-medium text-lg mb-1">{pdf.title}</h4>
                                <p className="text-sm text-gray-600 mb-1">{pdf.authors}</p>
                                <p className="text-sm text-gray-600 mb-2">
                                  {pdf.journal} • {pdf.year}
                                </p>
                                <div className="space-x-2">
                                  {pdf.pubmed_url && (
                                    <a
                                      href={pdf.pubmed_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center px-3 py-1 bg-purple-600 text-white text-sm rounded-md hover:bg-purple-700"
                                    >
                                      PubMed
                                    </a>
                                  )}
                                  
                                  {pdf.doi ? (
                                    <>
                                      <a
                                        href={pdf.access_urls.doi || undefined}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center px-3 py-1 bg-gray-600 text-white text-sm rounded-md hover:bg-gray-700"
                                      >
                                        Publisher Site
                                      </a>
                                      <a
                                        href={pdf.access_urls.scihub || undefined}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex items-center px-3 py-1 bg-red-600 text-white text-sm rounded-md hover:bg-red-700"
                                      >
                                        Try Sci-Hub
                                      </a>
                                    </>
                                  ) : (
                                    <span className="inline-flex items-center px-3 py-1 bg-gray-200 text-gray-700 text-sm rounded-md">
                                      No DOI Available
                                    </span>
                                  )}
                                </div>
                                <div className="mt-2">
                                  <button
                                    onClick={() => {
                                      const elem = document.getElementById(`abstract-${index}`);
                                      if (elem) {
                                        elem.style.display = elem.style.display === 'none' ? 'block' : 'none';
                                      }
                                    }}
                                    className="text-sm text-blue-600 hover:text-blue-800"
                                  >
                                    Show/Hide Abstract
                                  </button>
                                  <p
                                    id={`abstract-${index}`}
                                    className="mt-2 text-sm text-gray-600"
                                    style={{ display: 'none' }}
                                  >
                                    {pdf.abstract}
                                  </p>
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                </div>

                {totalPages > 1 && (
                  <div className="px-4 py-3 border-t flex items-center justify-center space-x-2">
                    <Button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      variant="outline"
                      size="sm"
                    >
                      Previous
                    </Button>
                    <span className="text-sm">
                      Page {page} of {totalPages}
                    </span>
                    <Button
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      variant="outline"
                      size="sm"
                    >
                      Next
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </main>
      <footer className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 py-4">
        <div className="max-w-4xl mx-auto px-4 flex items-center justify-center space-x-4">
          <p className="text-gray-600 font-medium italic">If you're not sloppin', you're not waging hard enough. You'll get enough pubs one day.</p>
        </div>
      </footer>
    </>
  );
}
