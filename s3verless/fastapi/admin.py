"""Admin interface generator for S3verless models."""

from s3verless.core.registry import get_all_metadata
from s3verless.core.settings import S3verlessSettings


def generate_admin_interface(settings: S3verlessSettings) -> str:
    """Generate a simple admin interface HTML."""
    metadata_dict = get_all_metadata()

    # Build model list
    model_items = []
    for model_name, metadata in metadata_dict.items():
        if metadata.enable_admin:
            model_items.append(f"""
                <li class="model-item">
                    <a href="#" onclick="loadModel('{model_name}', '{metadata.api_prefix}')">
                        <span class="model-icon">📄</span>
                        {metadata.plural_name.title()}
                    </a>
                </li>
            """)

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>S3verless Admin</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: #f5f5f5;
                color: #333;
            }}
            
            .header {{
                background-color: #2c3e50;
                color: white;
                padding: 1rem 2rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .header h1 {{
                font-size: 1.5rem;
                font-weight: 300;
                margin: 0;
            }}
            
            .header-actions {{
                display: flex;
                gap: 1rem;
                align-items: center;
            }}
            
            .header-actions .auth-status {{
                font-size: 0.875rem;
                color: #ecf0f1;
            }}
            
            .header-actions button {{
                padding: 0.5rem 1rem;
                background: #e74c3c;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.875rem;
            }}
            
            .header-actions button:hover {{
                background: #c0392b;
            }}
            
            .container {{
                display: flex;
                min-height: calc(100vh - 60px);
            }}
            
            .sidebar {{
                width: 250px;
                background-color: #34495e;
                padding: 1rem;
            }}
            
            .sidebar h2 {{
                color: #ecf0f1;
                font-size: 0.875rem;
                text-transform: uppercase;
                margin-bottom: 1rem;
                opacity: 0.7;
            }}
            
            .model-list {{
                list-style: none;
            }}
            
            .model-item {{
                margin-bottom: 0.5rem;
            }}
            
            .model-item a {{
                display: flex;
                align-items: center;
                padding: 0.75rem 1rem;
                color: #ecf0f1;
                text-decoration: none;
                border-radius: 4px;
                transition: background-color 0.2s;
            }}
            
            .model-item a:hover {{
                background-color: #2c3e50;
            }}
            
            .model-icon {{
                margin-right: 0.5rem;
            }}
            
            .content {{
                flex: 1;
                padding: 2rem;
                background-color: white;
                margin: 1rem;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            
            .content h2 {{
                margin-bottom: 1rem;
                color: #2c3e50;
            }}
            
            .data-table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 1rem;
            }}
            
            .data-table th,
            .data-table td {{
                padding: 0.75rem;
                text-align: left;
                border-bottom: 1px solid #e0e0e0;
            }}
            
            .data-table th {{
                background-color: #f8f9fa;
                font-weight: 600;
                color: #495057;
            }}
            
            .data-table tr:hover {{
                background-color: #f8f9fa;
            }}
            
            .btn {{
                display: inline-block;
                padding: 0.5rem 1rem;
                background-color: #3498db;
                color: white;
                text-decoration: none;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.875rem;
                transition: background-color 0.2s;
            }}
            
            .btn:hover {{
                background-color: #2980b9;
            }}
            
            .btn-danger {{
                background-color: #e74c3c;
            }}
            
            .btn-danger:hover {{
                background-color: #c0392b;
            }}
            
            .actions {{
                display: flex;
                gap: 0.5rem;
                margin-bottom: 1rem;
            }}
            
            .loading {{
                text-align: center;
                padding: 2rem;
                color: #7f8c8d;
            }}
            
            .empty-state {{
                text-align: center;
                padding: 3rem;
                color: #7f8c8d;
            }}
            
            .empty-state h3 {{
                margin-bottom: 1rem;
                color: #95a5a6;
            }}
            
            .pagination {{
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 1rem;
                margin-top: 2rem;
            }}
            
            .pagination button {{
                padding: 0.5rem 1rem;
                border: 1px solid #ddd;
                background: white;
                border-radius: 4px;
                cursor: pointer;
            }}
            
            .pagination button:disabled {{
                opacity: 0.5;
                cursor: not-allowed;
            }}
            
            .modal {{
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.5);
                z-index: 1000;
            }}
            
            .modal-content {{
                position: relative;
                background-color: white;
                margin: 5% auto;
                padding: 0;
                width: 90%;
                max-width: 600px;
                max-height: 85vh;
                border-radius: 8px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
                display: flex;
                flex-direction: column;
            }}
            
            .modal-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1.5rem 2rem;
                border-bottom: 1px solid #e0e0e0;
                flex-shrink: 0;
            }}
            
            #modal-form {{
                display: flex;
                flex-direction: column;
                flex: 1;
                overflow: hidden;
            }}
            
            #form-fields {{
                flex: 1;
                overflow-y: auto;
                padding: 1.5rem 2rem;
            }}
            
            #modal-form .actions {{
                flex-shrink: 0;
                padding: 1.5rem 2rem;
                border-top: 1px solid #e0e0e0;
                background-color: #f9f9f9;
                margin: 0;
            }}
            
            .close {{
                font-size: 1.5rem;
                cursor: pointer;
                color: #999;
            }}
            
            .form-group {{
                margin-bottom: 1rem;
            }}
            
            .form-group label {{
                display: block;
                margin-bottom: 0.5rem;
                font-weight: 500;
            }}
            
            .form-group input,
            .form-group textarea,
            .form-group select {{
                width: 100%;
                padding: 0.5rem;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 1rem;
            }}
            
            .form-group textarea {{
                resize: vertical;
                min-height: 100px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>S3verless Admin</h1>
            <div class="header-actions">
                <span class="auth-status" id="auth-status"></span>
                <button onclick="logout()" id="logout-btn" style="display: none;">Logout</button>
            </div>
        </div>
        
        <div class="container">
            <aside class="sidebar">
                <h2>Models</h2>
                <ul class="model-list">
                    {"".join(model_items)}
                </ul>
            </aside>
            
            <main class="content" id="content">
                <div class="empty-state">
                    <h3>Welcome to S3verless Admin</h3>
                    <p>Select a model from the sidebar to get started</p>
                </div>
            </main>
        </div>
        
        <!-- Create/Edit Modal -->
        <div id="modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2 id="modal-title">Create Item</h2>
                    <span class="close" onclick="closeModal()">&times;</span>
                </div>
                <form id="modal-form">
                    <div id="form-fields"></div>
                    <div class="actions">
                        <button type="submit" class="btn">Save</button>
                        <button type="button" class="btn btn-danger" onclick="closeModal()">Cancel</button>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            let currentModel = null;
            let currentApiPrefix = null;
            let currentPage = 1;
            let currentItem = null;
            let modelSchemas = null;
            let authToken = localStorage.getItem('s3verless_admin_token');
            
            // Check if logged in on page load
            window.addEventListener('DOMContentLoaded', () => {{
                if (!authToken) {{
                    showLoginPrompt();
                }} else {{
                    loadSchemas();
                }}
            }});
            
            function showLoginPrompt() {{
                const content = document.getElementById('content');
                content.innerHTML = `
                    <div style="max-width: 400px; margin: 2rem auto; padding: 2rem; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        <h2 style="margin-bottom: 1.5rem;">Admin Login</h2>
                        <p style="color: #666; margin-bottom: 1.5rem;">
                            This admin interface requires authentication for models with ownership protection.
                        </p>
                        <form id="login-form" style="display: flex; flex-direction: column; gap: 1rem;">
                            <div>
                                <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Username</label>
                                <input type="text" id="username" required style="width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px;" />
                            </div>
                            <div>
                                <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Password</label>
                                <input type="password" id="password" required style="width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px;" />
                            </div>
                            <button type="submit" class="btn" style="margin-top: 0.5rem;">Login</button>
                        </form>
                        <p style="color: #999; font-size: 0.875rem; margin-top: 1.5rem;">
                            💡 Tip: Register a user first at <a href="/docs" style="color: #3498db;">/register</a> or use the API docs
                        </p>
                        <button onclick="skipAuth()" class="btn" style="margin-top: 1rem; background: #95a5a6;">
                            Skip (Browse Only)
                        </button>
                    </div>
                `;
                
                document.getElementById('login-form').addEventListener('submit', handleLogin);
            }}
            
            async function handleLogin(e) {{
                e.preventDefault();
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                try {{
                    const response = await fetch('/token', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                        body: `username=${{encodeURIComponent(username)}}&password=${{encodeURIComponent(password)}}`
                    }});
                    
                    if (response.ok) {{
                        const data = await response.json();
                        authToken = data.access_token;
                        localStorage.setItem('s3verless_admin_token', authToken);
                        
                        // Clear login form and load admin
                        document.getElementById('content').innerHTML = `
                            <div class="empty-state">
                                <h3>✅ Login Successful!</h3>
                                <p>Select a model from the sidebar to get started</p>
                            </div>
                        `;
                        loadSchemas();
                    }} else {{
                        const error = await response.text();
                        alert('Login failed: ' + error);
                    }}
                }} catch (error) {{
                    alert('Login error: ' + error.message);
                }}
            }}
            
            function skipAuth() {{
                authToken = null;
                localStorage.removeItem('s3verless_admin_token');
                document.getElementById('content').innerHTML = `
                    <div class="empty-state">
                        <h3>Browse Mode (Read-Only)</h3>
                        <p>Select a model from the sidebar. You can view data but may not be able to create/edit/delete.</p>
                    </div>
                `;
                loadSchemas();
            }}
            
            function logout() {{
                authToken = null;
                localStorage.removeItem('s3verless_admin_token');
                location.reload();
            }}
            
            // Load OpenAPI schema
            async function loadSchemas() {{
                try {{
                    const response = await fetch('/openapi.json');
                    const openapi = await response.json();
                    modelSchemas = openapi.components?.schemas || {{}};
                }} catch (error) {{
                    console.error('Failed to load schemas:', error);
                    modelSchemas = {{}};
                }}
            }}
            
            async function loadModel(modelName, apiPrefix) {{
                currentModel = modelName;
                currentApiPrefix = apiPrefix;
                currentPage = 1;
                await loadData();
            }}
            
            async function loadData() {{
                const content = document.getElementById('content');
                content.innerHTML = '<div class="loading">Loading...</div>';
                
                // Update auth status in header
                updateAuthStatus();
                
                try {{
                    const headers = {{}};
                    if (authToken) {{
                        headers['Authorization'] = `Bearer ${{authToken}}`;
                    }}
                    
                    const response = await fetch(`${{currentApiPrefix}}?page=${{currentPage}}&page_size=10`, {{ headers }});
                    
                    if (!response.ok) {{
                        const errorText = await response.text();
                        let errorMessage = errorText;
                        try {{
                            const errorData = JSON.parse(errorText);
                            errorMessage = errorData.detail || errorData.message || errorText;
                        }} catch (e) {{
                            // Not JSON, use text as-is
                        }}
                        throw new Error(`HTTP ${{response.status}}: ${{errorMessage}}`);
                    }}
                    
                    const data = await response.json();
                    renderTable(data);
                }} catch (error) {{
                    content.innerHTML = `
                        <div class="empty-state">
                            <h3>Error loading data</h3>
                            <p>${{error.message}}</p>
                            <p style="font-size: 0.875rem; color: #666;">
                                Make sure your S3 bucket exists and is accessible. 
                                For local development, ensure LocalStack is running or set valid AWS credentials.
                            </p>
                        </div>
                    `;
                }}
            }}
            
            function renderTable(data) {{
                const content = document.getElementById('content');
                
                if (!data.items || data.items.length === 0) {{
                    content.innerHTML = `
                        <h2>${{currentModel}}</h2>
                        <div class="actions">
                            <button class="btn" onclick="showCreateModal()">Create New</button>
                        </div>
                        <div class="empty-state">
                            <h3>No items found</h3>
                            <p>Create your first item to get started</p>
                        </div>
                    `;
                    return;
                }}
                
                // Get columns from first item
                const columns = Object.keys(data.items[0]).filter(col => !col.startsWith('_'));
                
                let tableHtml = `
                    <h2>${{currentModel}}</h2>
                    <div class="actions">
                        <button class="btn" onclick="showCreateModal()">Create New</button>
                        <button class="btn" onclick="loadData()">Refresh</button>
                    </div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                ${{columns.map(col => `<th>${{col}}</th>`).join('')}}
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                data.items.forEach(item => {{
                    tableHtml += '<tr>';
                    columns.forEach(col => {{
                        let value = item[col];
                        if (value instanceof Object) {{
                            value = JSON.stringify(value);
                        }}
                        tableHtml += `<td>${{value || '-'}}</td>`;
                    }});
                    tableHtml += `
                        <td>
                            <button class="btn" onclick='editItem(${{JSON.stringify(item)}})'>Edit</button>
                            <button class="btn btn-danger" onclick="deleteItem('${{item.id}}')">Delete</button>
                        </td>
                    `;
                    tableHtml += '</tr>';
                }});
                
                tableHtml += `
                        </tbody>
                    </table>
                    <div class="pagination">
                        <button onclick="previousPage()" ${{!data.has_prev ? 'disabled' : ''}}>Previous</button>
                        <span>Page ${{data.page}} of ${{Math.ceil(data.total_count / data.page_size)}}</span>
                        <button onclick="nextPage()" ${{!data.has_next ? 'disabled' : ''}}>Next</button>
                    </div>
                `;
                
                content.innerHTML = tableHtml;
            }}
            
            function showCreateModal() {{
                currentItem = null;
                document.getElementById('modal-title').textContent = 'Create ' + currentModel;
                document.getElementById('modal').style.display = 'block';
                generateForm();
            }}
            
            function editItem(item) {{
                currentItem = item;
                document.getElementById('modal-title').textContent = 'Edit ' + currentModel;
                document.getElementById('modal').style.display = 'block';
                generateForm(item);
            }}
            
            function closeModal() {{
                document.getElementById('modal').style.display = 'none';
                currentItem = null;
            }}
            
            async function generateForm(item = null) {{
                const formFields = document.getElementById('form-fields');
                formFields.innerHTML = '';
                
                if (item) {{
                    // Edit mode - generate fields based on item
                    Object.entries(item).forEach(([key, value]) => {{
                        if (!['id', 'created_at', 'updated_at'].includes(key) && !key.startsWith('_')) {{
                            const inputType = getInputType(key, value);
                            const fieldHtml = `
                                <div class="form-group">
                                    <label for="${{key}}">${{formatFieldName(key)}}</label>
                                    <input type="${{inputType}}" id="${{key}}" name="${{key}}" value="${{value || ''}}" />
                                </div>
                            `;
                            formFields.innerHTML += fieldHtml;
                        }}
                    }});
                }} else {{
                    // Create mode - try to get schema from OpenAPI
                    const createSchema = modelSchemas?.[`${{currentModel}}Create`];
                    
                    if (createSchema?.properties) {{
                        // Generate fields from schema
                        Object.entries(createSchema.properties).forEach(([key, fieldSchema]) => {{
                            const required = createSchema.required?.includes(key) || false;
                            const inputType = getInputTypeFromSchema(fieldSchema);
                            
                            let fieldHtml = '';
                            
                            // Handle enum fields as dropdowns
                            if (fieldSchema.enum) {{
                                const options = fieldSchema.enum.map(val => 
                                    `<option value="${{val}}">${{val}}</option>`
                                ).join('');
                                fieldHtml = `
                                    <div class="form-group">
                                        <label for="${{key}}">${{formatFieldName(key)}}${{required ? ' *' : ''}}</label>
                                        <select id="${{key}}" name="${{key}}" ${{required ? 'required' : ''}}>
                                            <option value="">-- Select --</option>
                                            ${{options}}
                                        </select>
                                    </div>
                                `;
                            }} else {{
                                fieldHtml = `
                                    <div class="form-group">
                                        <label for="${{key}}">${{formatFieldName(key)}}${{required ? ' *' : ''}}</label>
                                        <input 
                                            type="${{inputType}}" 
                                            id="${{key}}" 
                                            name="${{key}}" 
                                            ${{required ? 'required' : ''}}
                                            placeholder="${{fieldSchema.description || ''}}"
                                            data-optional="${{!required}}"
                                        />
                                    </div>
                                `;
                            }}
                            
                            formFields.innerHTML += fieldHtml;
                        }});
                    }} else {{
                        // Fallback - basic name field
                        formFields.innerHTML = `
                            <div class="form-group">
                                <label for="name">Name</label>
                                <input type="text" id="name" name="name" required />
                            </div>
                            <p style="color: #666; font-size: 0.875rem;">
                                Schema not available. Add fields manually or edit an existing item to see all fields.
                            </p>
                        `;
                    }}
                }}
            }}
            
            function formatFieldName(key) {{
                return key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
            }}
            
            function getInputType(key, value) {{
                if (key.includes('email')) return 'email';
                if (key.includes('password')) return 'password';
                if (key.includes('url') || key.includes('link')) return 'url';
                if (key.includes('date') || key.includes('time')) return 'datetime-local';
                if (typeof value === 'number') return 'number';
                if (typeof value === 'boolean') return 'checkbox';
                return 'text';
            }}
            
            function getInputTypeFromSchema(fieldSchema) {{
                if (fieldSchema.format === 'email') return 'email';
                if (fieldSchema.format === 'password') return 'password';
                if (fieldSchema.format === 'uri') return 'url';
                if (fieldSchema.format === 'date-time') return 'datetime-local';
                if (fieldSchema.type === 'number' || fieldSchema.type === 'integer') return 'number';
                if (fieldSchema.type === 'boolean') return 'checkbox';
                return 'text';
            }}
            
            document.getElementById('modal-form').addEventListener('submit', async (e) => {{
                e.preventDefault();
                
                const formData = new FormData(e.target);
                const data = {{}};
                
                // Build data object, handling optional fields and type conversions
                const inputs = e.target.querySelectorAll('input, select, textarea');
                inputs.forEach(input => {{
                    const key = input.name;
                    const value = input.value;
                    const isOptional = input.getAttribute('data-optional') === 'true';
                    const isRequired = input.hasAttribute('required');
                    
                    // Skip empty optional fields completely
                    if (!isRequired && (!value || value === '')) {{
                        return;
                    }}
                    
                    // Convert types based on input type
                    if (input.type === 'number') {{
                        data[key] = value ? Number(value) : 0;
                    }} else if (input.type === 'checkbox') {{
                        data[key] = input.checked;
                    }} else if (input.tagName === 'SELECT') {{
                        // Only include select value if something is selected
                        if (value) {{
                            data[key] = value;
                        }}
                    }} else if (input.type === 'datetime-local') {{
                        // Only include datetime if provided
                        if (value) {{
                            data[key] = value;
                        }}
                    }} else {{
                        data[key] = value;
                    }}
                }});
                
                try {{
                    const headers = {{'Content-Type': 'application/json'}};
                    if (authToken) {{
                        headers['Authorization'] = `Bearer ${{authToken}}`;
                    }}
                    
                    let response;
                    if (currentItem) {{
                        // Update
                        response = await fetch(`${{currentApiPrefix}}/${{currentItem.id}}`, {{
                            method: 'PUT',
                            headers: headers,
                            body: JSON.stringify(data)
                        }});
                    }} else {{
                        // Create
                        response = await fetch(currentApiPrefix, {{
                            method: 'POST',
                            headers: headers,
                            body: JSON.stringify(data)
                        }});
                    }}
                    
                    if (response.ok) {{
                        closeModal();
                        loadData();
                    }} else {{
                        const errorText = await response.text();
                        let errorMessage = errorText;
                        try {{
                            const errorData = JSON.parse(errorText);
                            errorMessage = errorData.detail || errorData.message || errorText;
                        }} catch (e) {{
                            // Not JSON, use text as-is
                        }}
                        alert(`Error saving item: ${{errorMessage}}`);
                    }}
                }} catch (error) {{
                    alert('Error: ' + error.message);
                }}
            }});
            
            async function deleteItem(id) {{
                if (!confirm('Are you sure you want to delete this item?')) {{
                    return;
                }}
                
                try {{
                    const headers = {{}};
                    if (authToken) {{
                        headers['Authorization'] = `Bearer ${{authToken}}`;
                    }}
                    
                    const response = await fetch(`${{currentApiPrefix}}/${{id}}`, {{
                        method: 'DELETE',
                        headers: headers
                    }});
                    
                    if (response.ok) {{
                        loadData();
                    }} else {{
                        const errorText = await response.text();
                        let errorMessage = errorText;
                        try {{
                            const errorData = JSON.parse(errorText);
                            errorMessage = errorData.detail || errorData.message || errorText;
                        }} catch (e) {{
                            // Not JSON, use text as-is
                        }}
                        alert(`Error deleting item: ${{errorMessage}}`);
                    }}
                }} catch (error) {{
                    alert('Error: ' + error.message);
                }}
            }}
            
            function previousPage() {{
                if (currentPage > 1) {{
                    currentPage--;
                    loadData();
                }}
            }}
            
            function nextPage() {{
                currentPage++;
                loadData();
            }}
            
            function updateAuthStatus() {{
                const statusEl = document.getElementById('auth-status');
                const logoutBtn = document.getElementById('logout-btn');
                
                if (authToken) {{
                    statusEl.textContent = '🔒 Authenticated';
                    logoutBtn.style.display = 'block';
                }} else {{
                    statusEl.textContent = '🔓 Not Authenticated';
                    logoutBtn.style.display = 'none';
                }}
            }}
            
            // Update status on load
            updateAuthStatus();
            
            // Close modal when clicking outside
            window.onclick = function(event) {{
                const modal = document.getElementById('modal');
                if (event.target == modal) {{
                    closeModal();
                }}
            }}
        </script>
    </body>
    </html>
    """

    return html
