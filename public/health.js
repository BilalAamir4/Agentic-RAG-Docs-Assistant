window.addEventListener("DOMContentLoaded", () => {
  fetch("/api/health")
    .then((response) => response.json())
    .then((data) => {
      const output = document.getElementById("health-output");
      if (output) {
        output.textContent = JSON.stringify(data, null, 2);
      }
    })
    .catch((error) => {
      const output = document.getElementById("health-output");
      if (output) {
        output.textContent = "Error: " + error;
      }
    });
});
