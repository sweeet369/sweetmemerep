// Memecoin Trading Analyzer - Web Interface JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash');
    flashMessages.forEach(function(flash) {
        setTimeout(function() {
            flash.style.opacity = '0';
            flash.style.transition = 'opacity 0.5s';
            setTimeout(function() {
                flash.remove();
            }, 500);
        }, 5000);
    });

    // Add loading state to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.dataset.originalText = submitBtn.textContent;
                submitBtn.textContent = '⏳ Processing...';
            }
        });
    });

    // Token address validation
    const addressInput = document.getElementById('contract_address');
    if (addressInput) {
        addressInput.addEventListener('blur', function() {
            const address = this.value.trim();
            if (address && address.length < 32) {
                showValidationError(this, 'Contract address seems too short. Please verify.');
            } else {
                clearValidationError(this);
            }
        });
    }

    // Decision button active state
    const decisionBtns = document.querySelectorAll('.decision-btn');
    decisionBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            // Remove active class from all buttons
            decisionBtns.forEach(function(b) {
                b.classList.remove('active');
            });
            // Add active class to clicked button
            this.classList.add('active');
        });
    });

    // Auto-refresh token data every 60 seconds on detail page
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        // Auto-refresh every 60 seconds
        setInterval(function() {
            if (!refreshBtn.disabled) {
                refreshBtn.click();
            }
        }, 60000);
    }

    // Search/filter functionality for sources table
    const sourcesTable = document.querySelector('.sources-table');
    if (sourcesTable) {
        addTableSearch(sourcesTable);
    }

    // Copy contract address to clipboard
    const addressElements = document.querySelectorAll('.address');
    addressElements.forEach(function(el) {
        el.style.cursor = 'pointer';
        el.title = 'Click to copy';
        el.addEventListener('click', function() {
            copyToClipboard(this.textContent);
            showTooltip(this, 'Copied!');
        });
    });
});

// Refresh token data via API
function refreshToken(callId) {
    const btn = document.getElementById('refresh-btn');
    if (!btn) return;
    
    btn.disabled = true;
    btn.textContent = '⏳ Refreshing...';
    
    fetch(`/api/refresh_token/${callId}`, { 
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        if (data.success) {
            // Show success message
            showNotification('Token data refreshed successfully!', 'success');
            // Reload page after short delay
            setTimeout(function() {
                location.reload();
            }, 1000);
        } else {
            showNotification('Failed to refresh: ' + data.error, 'error');
            btn.disabled = false;
            btn.textContent = '🔄 Refresh Data';
        }
    })
    .catch(function(error) {
        showNotification('Error: ' + error.message, 'error');
        btn.disabled = false;
        btn.textContent = '🔄 Refresh Data';
    });
}

// Show validation error
function showValidationError(input, message) {
    clearValidationError(input);
    
    input.style.borderColor = '#ef4444';
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'validation-error';
    errorDiv.style.color = '#ef4444';
    errorDiv.style.fontSize = '0.85rem';
    errorDiv.style.marginTop = '0.25rem';
    errorDiv.textContent = message;
    
    input.parentNode.appendChild(errorDiv);
}

// Clear validation error
function clearValidationError(input) {
    input.style.borderColor = '';
    const errorDiv = input.parentNode.querySelector('.validation-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

// Copy text to clipboard
function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text);
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
        } catch (err) {
            console.error('Failed to copy:', err);
        }
        
        document.body.removeChild(textArea);
    }
}

// Show tooltip
function showTooltip(element, message) {
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    tooltip.textContent = message;
    tooltip.style.cssText = `
        position: absolute;
        background: #10b981;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        font-size: 0.85rem;
        z-index: 1000;
        pointer-events: none;
    `;
    
    const rect = element.getBoundingClientRect();
    tooltip.style.left = rect.left + 'px';
    tooltip.style.top = (rect.top - 40) + 'px';
    
    document.body.appendChild(tooltip);
    
    setTimeout(function() {
        tooltip.remove();
    }, 2000);
}

// Show notification
function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `flash flash-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10000;
        padding: 1rem 1.5rem;
        border-radius: 10px;
        font-weight: 500;
        animation: slideIn 0.3s ease;
    `;
    
    if (type === 'success') {
        notification.style.backgroundColor = 'rgba(16, 185, 129, 0.9)';
        notification.style.color = 'white';
    } else if (type === 'error') {
        notification.style.backgroundColor = 'rgba(239, 68, 68, 0.9)';
        notification.style.color = 'white';
    }
    
    document.body.appendChild(notification);
    
    setTimeout(function() {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.5s';
        setTimeout(function() {
            notification.remove();
        }, 500);
    }, 3000);
}

// Add search functionality to table
function addTableSearch(table) {
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = 'Search sources...';
    searchInput.className = 'form-input';
    searchInput.style.cssText = 'max-width: 300px; margin-bottom: 1rem;';
    
    table.parentNode.insertBefore(searchInput, table);
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const rows = table.querySelectorAll('tbody tr');
        
        rows.forEach(function(row) {
            const text = row.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        });
    });
}

// Format currency for display
function formatCurrency(value) {
    if (value === null || value === undefined) return 'N/A';
    
    value = parseFloat(value);
    if (isNaN(value)) return 'N/A';
    
    if (value >= 1000000000) {
        return '$' + (value / 1000000000).toFixed(2) + 'B';
    } else if (value >= 1000000) {
        return '$' + (value / 1000000).toFixed(2) + 'M';
    } else if (value >= 1000) {
        return '$' + (value / 1000).toFixed(2) + 'K';
    } else {
        return '$' + value.toFixed(2);
    }
}

// Format percentage
function formatPercentage(value) {
    if (value === null || value === undefined) return 'N/A';
    
    value = parseFloat(value);
    if (isNaN(value)) return 'N/A';
    
    const sign = value >= 0 ? '+' : '';
    return sign + value.toFixed(1) + '%';
}

// Add CSS animation for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);