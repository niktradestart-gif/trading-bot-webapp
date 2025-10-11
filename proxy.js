// proxy.js
export default async function handler(request) {
  const url = new URL(request.url);
  const apiUrl = url.searchParams.get('url');
  
  const response = await fetch(apiUrl);
  const data = await response.json();
  
  return new Response(JSON.stringify(data), {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Content-Type': 'application/json'
    }
  });
}
