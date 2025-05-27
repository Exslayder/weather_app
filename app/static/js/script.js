const inp = document.getElementById("city-input");
const list = document.getElementById("suggestions");
const form = document.getElementById("weather-form");

inp.addEventListener("input", async () => {
  const q = inp.value.trim();
  if (q.length < 2) {
    list.innerHTML = "";
    return;
  }
  const resp = await fetch(
    `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(q)}&count=5`
  );
  const data = await resp.json();
  list.innerHTML = (data.results || []).map(r => {
    const label = `${r.name}, ${r.country}`;
    return `<li class="p-2 hover:bg-gray-200 cursor-pointer" data-full="${label}">${label}</li>`;
  }).join("");
});

list.addEventListener("click", e => {
  const li = e.target.closest("li");
  if (!li) return;
  inp.value = li.getAttribute("data-full");
  list.innerHTML = "";
});

function selectLastCity() {
  const inpField = document.getElementById("city-input");
  const last = inpField.getAttribute("value") || inpField.value || "";
  if (!last) return;
  inpField.value = last;
}
