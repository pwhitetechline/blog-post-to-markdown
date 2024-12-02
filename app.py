from flask import Flask, request, jsonify, render_template, send_file
import requests
from bs4 import BeautifulSoup
import html2text
import re
from datetime import datetime
from urllib.parse import urlparse
import io
from slugify import slugify

app = Flask(__name__)

def generate_front_matter(soup, url):
    """Generate YAML front matter from the page metadata"""
    front_matter = {
        'title': soup.title.string if soup.title else '',
        'date': datetime.now().strftime('%Y-%m-%d'),
        'url': url,
        'author': 'Julie Donnelly'
    }
    
    # Try to get meta description
    meta_desc = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'})
    if meta_desc:
        front_matter['description'] = meta_desc.get('content', '')
    
    # Format as YAML
    yaml = ['---']
    for key, value in front_matter.items():
        if value:
            # Clean the value of any newlines and quotes
            clean_value = str(value).replace('\n', ' ').replace('"', "'").strip()
            yaml.append(f'{key}: "{clean_value}"')
    yaml.append('---\n')
    
    return '\n'.join(yaml)

def clean_markdown(markdown_text):
    # Remove excessive newlines
    markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
    # Remove trailing whitespace
    markdown_text = '\n'.join(line.rstrip() for line in markdown_text.splitlines())
    return markdown_text.strip()

def generate_filename(url):
    """Generate a safe filename from the URL path"""
    try:
        # Parse the URL and get the path
        parsed_url = urlparse(url)
        path = parsed_url.path.rstrip('/')
        
        # Get the last part of the path
        path_parts = [p for p in path.split('/') if p]
        if not path_parts:
            return 'blog-post.md'
            
        # Use the last part of the path
        filename_base = path_parts[-1]
        
        # Remove any file extension if present
        filename_base = filename_base.rsplit('.', 1)[0]
        
        # Slugify the filename (convert to lowercase, replace spaces with hyphens)
        filename = slugify(filename_base)
        
        return f"{filename}.md" if filename else 'blog-post.md'
    except Exception as e:
        print(f"Error generating filename: {str(e)}")
        return 'blog-post.md'

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert():
    try:
        data = request.get_json()
        url = data.get('url')
        include_front_matter = data.get('includeFrontMatter', True)
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Fetch the content
        response = requests.get(url)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'footer', 'header']):
            element.decompose()
        
        # Generate front matter if requested
        front_matter = generate_front_matter(soup, url) if include_front_matter else ''
        
        # Convert to Markdown
        h = html2text.HTML2Text()
        h.body_width = 0  # Disable line wrapping
        markdown_text = h.handle(str(soup))
        
        # Clean up the markdown
        cleaned_markdown = clean_markdown(markdown_text)
        
        # Combine front matter and content
        final_markdown = front_matter + cleaned_markdown if include_front_matter else cleaned_markdown
        
        return jsonify({
            'markdown': final_markdown,
            'url': url  # Include the URL in the response
        })
    
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        markdown_content = data.get('markdown')
        url = data.get('url')
        
        if not markdown_content:
            return jsonify({'error': 'Markdown content is required'}), 400
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Generate filename from URL
        filename = generate_filename(url)
        
        # Create a file-like object in memory
        file_obj = io.BytesIO(markdown_content.encode('utf-8'))
        
        # Send the file with the correct filename and MIME type
        response = send_file(
            file_obj,
            mimetype='text/markdown',
            as_attachment=True,
            download_name=filename
        )
        
        # Add CORS headers if needed
        response.headers['Access-Control-Allow-Origin'] = '*'
        
        return response
        
    except Exception as e:
        print(f"Error in download: {str(e)}")
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
