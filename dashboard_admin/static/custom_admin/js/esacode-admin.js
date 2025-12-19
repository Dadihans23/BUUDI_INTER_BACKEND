// ESACODE ADMIN INTERACTIVE FEATURES

$(document).ready(function() {
    
    // Initialize all components
    initializeComponents();
    
    function initializeComponents() {
        initTokenToggle();
        initCopyToClipboard();
        initSearchFilters();
        initActionButtons();
        initTooltips();
        initAnimations();
        initDarkMode();
        initMobileMenu();
        initSubmenu();
    }

    // Token show/hide functionality
    function initTokenToggle() {
        $('.token-toggle').on('click', function() {
            const tokenElement = $(this).closest('.token-display');
            const isHidden = tokenElement.hasClass('hidden');
            
            if (isHidden) {
                tokenElement.removeClass('hidden');
                $(this).html('<i class="mdi mdi-eye-off"></i>');
                $(this).attr('title', 'Masquer le token');
            } else {
                tokenElement.addClass('hidden');
                $(this).html('<i class="mdi mdi-eye"></i>');
                $(this).attr('title', 'Afficher le token');
            }
        });
    }

    // Copy to clipboard functionality
    function initCopyToClipboard() {
        $('.copy-btn').on('click', function() {
            const textToCopy = $(this).data('copy');
            const btn = $(this);
            
            if (navigator.clipboard) {
                navigator.clipboard.writeText(textToCopy).then(function() {
                    showCopySuccess(btn);
                }).catch(function() {
                    fallbackCopy(textToCopy, btn);
                });
            } else {
                fallbackCopy(textToCopy, btn);
            }
        });
    }

    function fallbackCopy(text, btn) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        
        try {
            document.execCommand('copy');
            showCopySuccess(btn);
        } catch (err) {
            showCopyError(btn);
        }
        
        document.body.removeChild(textArea);
    }

    function showCopySuccess(btn) {
        const originalHtml = btn.html();
        btn.html('<i class="mdi mdi-check"></i>');
        btn.removeClass('btn-copy').addClass('btn-success');
        
        setTimeout(() => {
            btn.html(originalHtml);
            btn.removeClass('btn-success').addClass('btn-copy');
        }, 2000);
        
        showToast('Copié dans le presse-papiers !', 'success');
    }

    function showCopyError(btn) {
        showToast('Erreur lors de la copie', 'error');
    }

    // Search and filter functionality
    function initSearchFilters() {
        $('.search-input').on('input', function() {
            const searchTerm = $(this).val().toLowerCase();
            const tableRows = $('.table tbody tr');
            
            tableRows.each(function() {
                const rowText = $(this).text().toLowerCase();
                if (rowText.includes(searchTerm)) {
                    $(this).show().addClass('animate-fadein');
                } else {
                    $(this).hide().removeClass('animate-fadein');
                }
            });
            
            updateResultsCount(tableRows.filter(':visible').length);
        });

        // Status filter
        $('.status-filter').on('change', function() {
            const filterValue = $(this).val();
            const tableRows = $('.table tbody tr');
            
            if (filterValue === 'all') {
                tableRows.show();
            } else {
                tableRows.each(function() {
                    const statusBadge = $(this).find('.badge');
                    const status = statusBadge.text().toLowerCase();
                    
                    if (status.includes(filterValue)) {
                        $(this).show();
                    } else {
                        $(this).hide();
                    }
                });
            }
        });
    }

    function updateResultsCount(count) {
        let resultText = $('.results-count');
        if (resultText.length === 0) {
            resultText = $('<div class="results-count text-muted small mb-2"></div>');
            $('.table').before(resultText);
        }
        resultText.text(`${count} résultat(s) trouvé(s)`);
    }

    // Action buttons functionality
    function initActionButtons() {
        // View details
        $('.btn-view').on('click', function() {
            const id = $(this).data('id');
            const type = $(this).data('type');
            // showDetailsModal(id, type);
        });

        // Edit item
        $('.btn-edit').on('click', function() {
            const id = $(this).data('id');
            const type = $(this).data('type');
            // showEditModal(id, type);
        });

        // Delete item
        $('.btn-delete').on('click', function() {
            const id = $(this).data('id');
            const type = $(this).data('type');
            // showDeleteConfirmation(id, type);
        });

        // Bulk actions
        $('.select-all').on('change', function() {
            $('.row-checkbox').prop('checked', $(this).is(':checked'));
            updateBulkActions();
        });

        $('.row-checkbox').on('change', function() {
            updateBulkActions();
        });
    }

    function updateBulkActions() {
        const checkedCount = $('.row-checkbox:checked').length;
        const bulkActions = $('.bulk-actions');
        
        if (checkedCount > 0) {
            bulkActions.show().find('.count').text(checkedCount);
        } else {
            bulkActions.hide();
        }
    }

    // Enhanced Modal functions
    function showDetailsModal(id, type) {
        const modal = $('#detailsModal');
        
        // Update modal title with icon
        modal.find('.modal-title span').text(`Détails ${type} #${id}`);
        
        // Show loader
        modal.find('#detailsLoader').show();
        modal.find('.modal-body').children().not('#detailsLoader').hide();
        
        // Show action button
        modal.find('#detailsActionBtn').show().off('click').on('click', function() {
            window.location.href = `/admin/${type}/edit/${id}/`;
        });
        
        modal.modal('show');
        
        // Simulate data loading with enhanced UI
        setTimeout(() => {
            modal.find('#detailsLoader').hide();
            const content = getDetailsContent(id, type);
            modal.find('.modal-body').append(content);
            modal.find('.modal-body').children().not('#detailsLoader').show();
        }, 800);
    }

    function showEditModal(id, type) {
        const modal = $('#editModal');
        modal.find('.modal-title span').text(`Modifier ${type} #${id}`);
        
        // Show loader
        modal.find('#editLoader').show();
        modal.find('.modal-body').children().not('#editLoader').hide();
        
        modal.modal('show');
        
        // Enhanced save button functionality
        modal.find('#editSaveBtn').off('click').on('click', function() {
            saveModalData(id, type);
        });
        
        // Load form data
        setTimeout(() => {
            modal.find('#editLoader').hide();
            const form = getEditForm(id, type);
            modal.find('.modal-body').append(form);
            modal.find('.modal-body').children().not('#editLoader').show();
        }, 600);
    }

    function showDeleteConfirmation(id, type, itemName = '') {
        const modal = $('#deleteModal');
        
        // Customize warning text
        const warningText = itemName ? 
            `Vous êtes sur le point de supprimer "${itemName}". Cette action est irréversible.` :
            `Cette action supprimera définitivement cet élément et ne peut pas être annulée.`;
        
        modal.find('#deleteWarningText').text(warningText);
        
        // Enhanced delete button functionality
        modal.find('#confirmDeleteBtn').off('click').on('click', function() {
            performDelete(id, type, itemName);
        });
        
        modal.modal('show');
    }

    function performDelete(id, type, itemName) {
        // Show loading modal
        showLoadingModal('Suppression en cours...');
        
        // Hide delete modal
        $('#deleteModal').modal('hide');
        
        // Simulate delete operation
        setTimeout(() => {
            hideLoadingModal();
            showSuccessModal(`${itemName || 'L\'élément'} a été supprimé avec succès.`);
            
            // Remove row from table if exists
            $(`tr[data-id="${id}"]`).fadeOut(500, function() {
                $(this).remove();
                updateResultsCount($('.table tbody tr:visible').length);
            });
        }, 1500);
    }

    function saveModalData(id, type) {
        const form = $('.edit-form');
        const formData = form.serialize();
        
        // Show loading state
        $('#editSaveBtn').html('<i class="mdi mdi-loading mdi-spin me-1"></i> Sauvegarde...').prop('disabled', true);
        
        // Simulate save operation
        setTimeout(() => {
            $('#editModal').modal('hide');
            showSuccessModal('Les modifications ont été sauvegardées avec succès.');
            
            // Reset button
            $('#editSaveBtn').html('<i class="mdi mdi-content-save me-1"></i> Sauvegarder').prop('disabled', false);
        }, 1200);
    }

    function showLoadingModal(message = 'Traitement en cours...') {
        $('#loadingMessage').text(message);
        $('#loadingModal').modal('show');
    }

    function hideLoadingModal() {
        $('#loadingModal').modal('hide');
    }

    function showSuccessModal(message) {
        $('#successMessage').text(message);
        $('#successModal').modal('show');
    }

    // function getDetailsContent(id, type) {
    //     // Generate dynamic content based on type
    //     return `
    //         <div class="row">
    //             <div class="col-md-6">
    //                 <strong>ID:</strong> ${id}<br>
    //                 <strong>Type:</strong> ${type}<br>
    //                 <strong>Date de création:</strong> ${new Date().toLocaleDateString()}<br>
    //                 <strong>Statut:</strong> <span class="badge badge-success">Actif</span>
    //             </div>
    //             <div class="col-md-6">
    //                 <strong>Dernière modification:</strong> ${new Date().toLocaleDateString()}<br>
    //                 <strong>Modifié par:</strong> Admin<br>
    //             </div>
    //         </div>
    //         <hr>
    //         <h6>Informations supplémentaires</h6>
    //         <p>Contenu détaillé pour l'élément ${type} #${id}...</p>
    //     `;
    // }

    function getEditForm(id, type) {
        return `
            <form class="edit-form" data-id="${id}" data-type="${type}">
                <div class="form-group mb-3">
                    <label>Nom</label>
                    <input type="text" class="form-control" value="Élément ${id}">
                </div>
                <div class="form-group mb-3">
                    <label>Statut</label>
                    <select class="form-control">
                        <option value="active">Actif</option>
                        <option value="inactive">Inactif</option>
                    </select>
                </div>
                <div class="form-group mb-3">
                    <label>Description</label>
                    <textarea class="form-control" rows="3">Description de l'élément ${id}</textarea>
                </div>
            </form>
        `;
    }

    // Toast notifications
    function showToast(message, type = 'info') {
        const toastContainer = getToastContainer();
        const toast = $(`
            <div class="toast align-items-center text-white bg-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'primary'} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="mdi mdi-${type === 'success' ? 'check-circle' : type === 'error' ? 'alert-circle' : 'information'}"></i>
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `);
        
        toastContainer.append(toast);
        toast.toast({ delay: 3000 }).toast('show');
        
        toast.on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }

    function getToastContainer() {
        let container = $('.toast-container');
        if (container.length === 0) {
            container = $('<div class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 1060;"></div>');
            $('body').append(container);
        }
        return container;
    }

    // Initialize tooltips
    function initTooltips() {
        $('[data-bs-toggle="tooltip"]').tooltip();
        
        // Add dynamic tooltips
        $('.action-btn').each(function() {
            const action = $(this).hasClass('btn-view') ? 'Voir' : 
                          $(this).hasClass('btn-edit') ? 'Modifier' : 
                          $(this).hasClass('btn-delete') ? 'Supprimer' : 
                          $(this).hasClass('btn-copy') ? 'Copier' : 'Action';
            $(this).attr('title', action).tooltip();
        });
    }

    // Initialize animations
    function initAnimations() {
        // Animate cards on load
        $('.card').each(function(index) {
            $(this).css('animation-delay', `${index * 0.1}s`).addClass('animate-fadein');
        });

        // Smooth scrolling
        $('a[href^="#"]').on('click', function(e) {
            const href = $(this).attr('href');
            if (href && href !== '#' && href.length > 1) {
                e.preventDefault();
                const target = $(href);
                if (target.length) {
                    $('html, body').animate({
                        scrollTop: target.offset().top - 80
                    }, 500);
                }
            }
        });
    }

    // Dark mode toggle
    function initDarkMode() {
        const toggleBtn = $('#theme-toggle-switch');
        const currentTheme = localStorage.getItem('theme') || 'light';
        
        $('html').attr('data-bs-theme', currentTheme);
        updateThemeIcon(currentTheme);
        
        toggleBtn.on('click', function() {
            const currentTheme = $('html').attr('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            $('html').attr('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
            
            showToast(`Mode ${newTheme === 'dark' ? 'sombre' : 'clair'} activé`, 'success');
        });
    }

    // Dark mode toggle
    function initDarkMode() {
        const toggleBtn = $('#theme-toggle-switch');
        const currentTheme = localStorage.getItem('theme') || 'light';
        
        // Set initial theme
        $('html').attr('data-bs-theme', currentTheme);
        updateThemeIcon(currentTheme);
        
        // Toggle theme on click
        toggleBtn.on('click', function(e) {
            e.preventDefault();
            const currentTheme = $('html').attr('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            $('html').attr('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
            
            showToast(`Mode ${newTheme === 'dark' ? 'sombre' : 'clair'} activé`, 'success');
        });
    }

    function updateThemeIcon(theme) {
        const icon = $('#theme-toggle-switch i');
        if (theme === 'dark') {
            icon.removeClass('mdi-weather-night').addClass('mdi-weather-sunny');
        } else {
            icon.removeClass('mdi-weather-sunny').addClass('mdi-weather-night');
        }
    }

    // Mobile menu
    function initMobileMenu() {
        $('#sidebar-toggle-button').on('click', function() {
            $('.page-sidebar').toggleClass('show');
        });

        $(document).on('click', function(e) {
            if (!$(e.target).closest('.page-sidebar, #sidebar-toggle-button').length) {
                $('.page-sidebar').removeClass('show');
            }
        });
    }

    // Submenu functionality
    function initSubmenu() {
        $('.accordion-toggle').on('click', function(e) {
            e.preventDefault();
            const parent = $(this).closest('.has-submenu');
            const isOpen = parent.hasClass('open');
            
            // Close all other submenus
            $('.has-submenu').removeClass('open');
            
            // Toggle current submenu
            if (!isOpen) {
                parent.addClass('open');
            }
        });

        // Close submenu when clicking outside
        $(document).on('click', function(e) {
            if (!$(e.target).closest('.has-submenu').length) {
                $('.has-submenu').removeClass('open');
            }
        });
    }

    // Statistics refresh
    $('.refresh-stats').on('click', function() {
        const btn = $(this);
        const originalHtml = btn.html();
        
        btn.html('<i class="mdi mdi-loading mdi-spin"></i>').prop('disabled', true);
        
        // Simulate refresh
        setTimeout(() => {
            btn.html(originalHtml).prop('disabled', false);
            showToast('Statistiques mises à jour', 'success');
            
            // Animate numbers
            $('.widget-desk h4').each(function() {
                const element = $(this);
                const finalValue = parseInt(element.text().replace(/[^0-9]/g, ''));
                animateNumber(element, 0, finalValue, 1000);
            });
        }, 2000);
    });

    function animateNumber(element, start, end, duration) {
        const increment = (end - start) / (duration / 16);
        let current = start;
        
        const timer = setInterval(() => {
            current += increment;
            if (current >= end) {
                current = end;
                clearInterval(timer);
            }
            
            const text = element.text();
            const newText = text.replace(/\d+/, Math.floor(current));
            element.text(newText);
        }, 16);
    }

    // Auto-refresh data every 5 minutes
    setInterval(() => {
        if ($('.auto-refresh').length > 0) {
            console.log('Auto-refreshing data...');
            // Add your auto-refresh logic here
        }
    }, 5 * 60 * 1000);

    // Add loading states
    $(document).ajaxStart(function() {
        $('body').addClass('loading');
    }).ajaxStop(function() {
        $('body').removeClass('loading');
    });

    // Keyboard shortcuts
    $(document).on('keydown', function(e) {
        // Ctrl+K for search
        if (e.ctrlKey && e.key === 'k') {
            e.preventDefault();
            $('.search-input').focus();
        }
        
        // Escape to close modals
        if (e.key === 'Escape') {
            $('.modal').modal('hide');
        }
    });
    
    console.log('🎉 Esacode Admin initialized successfully!');
});

// Global utility functions
window.EsacodeAdmin = {
    showToast: function(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999;';
            document.body.appendChild(toastContainer);
        }
        
        const toastId = 'toast-' + Date.now();
        const bgClass = {
            'success': 'bg-success',
            'error': 'bg-danger', 
            'warning': 'bg-warning',
            'info': 'bg-info'
        }[type] || 'bg-info';
        
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0 mb-2" role="alert" style="min-width: 300px;">
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="document.getElementById('${toastId}').remove()"></button>
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        // Auto remove after 4 seconds
        setTimeout(() => {
            const toast = document.getElementById(toastId);
            if (toast) {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }
        }, 4000);
    },
    
    refreshData: function() {
        $('.refresh-stats').click();
    },
    
    exportData: function(format = 'csv') {
        console.log(`Exporting data in ${format} format...`);
        this.showToast(`Export ${format} en cours...`, 'info');
    }
};




