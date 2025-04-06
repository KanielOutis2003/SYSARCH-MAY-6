// Function to load announcement data for editing
function editAnnouncement(announcementId) {
    // Fetch announcement data
    fetch(`/admin/get-announcement/${announcementId}`)
        .then(response => response.json())
        .then(data => {
            // Fill the edit form with the announcement data
            document.getElementById('edit_announcement_id').value = data.id;
            document.getElementById('edit_title').value = data.title;
            document.getElementById('edit_content').value = data.content;
            
            // Show the edit modal
            var editModal = new bootstrap.Modal(document.getElementById('editAnnouncementModal'));
            editModal.show();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error fetching announcement data');
        });
}

// Apply styling to the Reset Semester button
document.addEventListener('DOMContentLoaded', function() {
    // Style the Reset Semester button
    const resetButton = document.querySelector('form[action*="reset_semester"] button');
    if (resetButton) {
        resetButton.classList.add('btn', 'btn-danger', 'mt-3');
        resetButton.innerHTML = '<i class="fas fa-redo"></i> Reset Semester';
    }
    
    // Add event listeners for announcement edit buttons
    const editButtons = document.querySelectorAll('.edit-announcement-btn');
    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            const announcementId = this.getAttribute('data-id');
            editAnnouncement(announcementId);
        });
    });
}); 