const toggle = document.getElementById('darkModeToggle');

if (toggle) {
    if (localStorage.getItem('darkMode') === 'enabled') {
        document.body.classList.add('dark-mode');
        toggle.innerText = '☀️ Light Mode';
    }

    toggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');

        if (document.body.classList.contains('dark-mode')) {
            localStorage.setItem('darkMode', 'enabled');
            toggle.innerText = '☀️ Light Mode';
        } else {
            localStorage.setItem('darkMode', 'disabled');
            toggle.innerText = '🌙 Dark Mode';
        }
    });
}
