// static/js/scene.js
// Manages the Three.js 3D orbit visualization.

let renderer, scene, camera, controls;
let orbitLineWith, orbitLineWithout;
const AU_SCALE = 1 / 1000;  // 1 AU → 0.001 scene units (1000 AU = 1 unit)

export function initScene(canvasEl) {
  renderer = new THREE.WebGLRenderer({ canvas: canvasEl, antialias: true });
  renderer.setSize(canvasEl.clientWidth, canvasEl.clientHeight);
  renderer.setPixelRatio(window.devicePixelRatio);

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000010);

  camera = new THREE.PerspectiveCamera(
    60,
    canvasEl.clientWidth / canvasEl.clientHeight,
    0.001,
    1e9
  );
  camera.position.set(0, 50, 100);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  _addLights();
  _addSun();
  _addPlanets();
  _addStarField();

  window.addEventListener("resize", () => {
    camera.aspect = canvasEl.clientWidth / canvasEl.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(canvasEl.clientWidth, canvasEl.clientHeight);
  });

  _animate();
}

function _animate() {
  requestAnimationFrame(_animate);
  controls.update();
  renderer.render(scene, camera);
}

function _addLights() {
  scene.add(new THREE.AmbientLight(0x404040));
  const sun_light = new THREE.PointLight(0xffffff, 2, 0);
  scene.add(sun_light);
}

function _addSun() {
  const geo = new THREE.SphereGeometry(2, 32, 32);
  const mat = new THREE.MeshBasicMaterial({ color: 0xffdd44 });
  scene.add(new THREE.Mesh(geo, mat));
}

function _addPlanets() {
  // Jupiter
  const jGeo = new THREE.SphereGeometry(0.8, 16, 16);
  const jMat = new THREE.MeshStandardMaterial({ color: 0xc88b3a });
  const jupiter = new THREE.Mesh(jGeo, jMat);
  jupiter.position.set(5.2 * AU_SCALE * 1000, 0, 0);  // at t=0
  scene.add(jupiter);

  // Saturn
  const sGeo = new THREE.SphereGeometry(0.6, 16, 16);
  const sMat = new THREE.MeshStandardMaterial({ color: 0xe4d191 });
  const saturn = new THREE.Mesh(sGeo, sMat);
  saturn.position.set(9.54 * AU_SCALE * 1000, 0, 0);

  // Saturn ring
  const ringGeo = new THREE.RingGeometry(0.9, 1.5, 32);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0xd4b483,
    side: THREE.DoubleSide,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 3;
  saturn.add(ring);
  scene.add(saturn);
}

function _addStarField() {
  const verts = [];
  for (let i = 0; i < 5000; i++) {
    verts.push(
      (Math.random() - 0.5) * 2000,
      (Math.random() - 0.5) * 2000,
      (Math.random() - 0.5) * 2000
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
  scene.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: 0xffffff, size: 0.3 })));
}

export function drawOrbits(trajectoryWithDM, trajectoryWithoutDM) {
  // Remove existing orbit lines
  if (orbitLineWith) scene.remove(orbitLineWith);
  if (orbitLineWithout) scene.remove(orbitLineWithout);

  orbitLineWith = _buildLine(trajectoryWithDM, 0xff8800);      // orange
  orbitLineWithout = _buildLine(trajectoryWithoutDM, 0xffffff); // white

  scene.add(orbitLineWith);
  scene.add(orbitLineWithout);

  // Fit camera to trajectory extent
  const maxR = Math.max(...trajectoryWithoutDM.map(
    ([x, y, z]) => Math.sqrt(x * x + y * y + z * z)
  ));
  const viewDist = maxR * AU_SCALE * 2.5;
  camera.position.set(viewDist * 0.6, viewDist * 0.4, viewDist);
  camera.far = viewDist * 20;
  camera.updateProjectionMatrix();
  controls.update();
}

function _buildLine(points, color) {
  const verts = points.flatMap(([x, y, z]) => [
    x * AU_SCALE, z * AU_SCALE, -y * AU_SCALE,  // y/z swap for Three.js convention
  ]);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
  return new THREE.Line(geo, new THREE.LineBasicMaterial({ color }));
}
