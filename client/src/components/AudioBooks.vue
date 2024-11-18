<template>
  <main role="main">
    <div class="container my-5">
      <!-- Refresh Library Button -->
      <div class="d-flex justify-content-between align-items-center mb-4">
        <h1 class="text-primary">Audiobook Manager</h1>
        <button @click="refreshLibrary" class="btn btn-outline-secondary">Refresh Library</button>
      </div>

      <!-- Section: Download New Audiobook -->
      <div class="card shadow-sm mb-5">
        <div class="card-header bg-primary text-white">
          <h2 class="h5 mb-0">Download a New Audiobook</h2>
        </div>
        <div class="card-body">
          <form @submit.prevent="downloadAudiobook">
            <div class="row">
              <div class="col-md-6 mb-3">
                <label for="url" class="form-label">YouTube URL</label>
                <input
                  type="text"
                  id="url"
                  class="form-control"
                  v-model="newAudiobook.url"
                  placeholder="Enter YouTube URL"
                  required
                />
              </div>
              <div class="col-md-6 mb-3">
                <label for="title" class="form-label">Title</label>
                <input
                  type="text"
                  id="title"
                  class="form-control"
                  v-model="newAudiobook.title"
                  placeholder="Enter Title"
                  required
                />
              </div>
              <div class="col-md-6 mb-3">
                <label for="artist" class="form-label">Artist</label>
                <input
                  type="text"
                  id="artist"
                  class="form-control"
                  v-model="newAudiobook.artist"
                  placeholder="Enter Artist"
                  required
                />
              </div>
              <div class="col-md-6 mb-3">
                <label for="album" class="form-label">Album</label>
                <input
                  type="text"
                  id="album"
                  class="form-control"
                  v-model="newAudiobook.album"
                  placeholder="Enter Album"
                  required
                />
              </div>
              <div class="col-md-12 mb-3">
                <label for="cover" class="form-label">Cover Image</label>
                <input
                  type="file"
                  id="cover"
                  class="form-control"
                  @change="onFileChange"
                />
              </div>
            </div>
            <button type="submit" class="btn btn-primary w-100">Download Audiobook</button>
          </form>
        </div>
      </div>

      <!-- Section: Available Audiobooks -->
      <div>
        <h2 class="h4 text-secondary mb-4">Available Audiobooks</h2>
        <div class="row">
          <div v-for="audiobook in audiobooks" :key="audiobook.id" class="col-md-4 col-lg-3 mb-4">
            <div class="card shadow-sm h-100">
              <div class="position-relative">
                <!-- Display cover if available -->
                <img
                  v-if="audiobook.cover_uri !== null"
                  :src="'./assets/covers/' + audiobook.cover_uri"
                  class="card-img-top"
                  :alt="audiobook.title"
                />
                <!-- Fallback for missing cover -->
                <svg
                  v-else
                  class="bd-placeholder-img card-img-top"
                  width="100%"
                  height="200"
                  xmlns="http://www.w3.org/2000/svg"
                  preserveAspectRatio="xMidYMid slice"
                  focusable="false"
                  role="img"
                  aria-label="Placeholder: Thumbnail"
                >
                  <title>No Cover</title>
                  <rect width="100%" height="100%" fill="#e9ecef" />
                  <text x="50%" y="50%" fill="#adb5bd" dy=".3em">No Cover</text>
                </svg>
              </div>
              <div class="card-body">
                <h5 class="card-title">{{ audiobook.title }}</h5>
                <p class="card-text text-muted mb-0">{{ audiobook.artist }}</p>
                <p class="card-text">
                  <small class="text-muted">{{ audiobook.album }}</small>
                </p>
              </div>
              <div class="card-footer bg-transparent border-0">
                <Tonies
                  :tonies="creativetonies"
                  :audiobookID="audiobook.id"
                  @onchange="uploadAlbumToTonie"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script>
import axios from "axios";
import Tonies from "./Tonies.vue";

const backendUrl = `${process.env.VUE_APP_BACKEND_SCHEME}://${process.env.VUE_APP_BACKEND_HOST}:${process.env.VUE_APP_BACKEND_PORT}`;

export default {
  components: { Tonies },
  data() {
    return {
      audiobooks: [],
      creativetonies: [],
      newAudiobook: {
        url: "",
        title: "",
        artist: "",
        album: "",
        coverFile: null,
      },
    };
  },
  methods: {
    getAudiobooks() {
      axios.get(`${backendUrl}/audiobooks`).then((res) => {
        this.audiobooks = res.data.audiobooks;
      }).catch((err) => console.error(err));
    },
    refreshLibrary() {
      axios.post(`${backendUrl}/refresh-library`).then(() => {
        console.log("Library refresh triggered.");
        setTimeout(() => this.getAudiobooks(), 3000);
      }).catch((err) => console.error(err));
    },
    getCreativeTonies() {
      axios.get(`${backendUrl}/creativetonies`).then((res) => {
        this.creativetonies = res.data.creativetonies;
      }).catch((err) => console.error(err));
    },
    uploadAlbumToTonie(tonieID, audiobookID) {
      axios.post(`${backendUrl}/upload`, { tonie_id: tonieID, audiobook_id: audiobookID })
        .then((res) => console.log("Upload ID:", res.data.upload_id))
        .catch((err) => console.error(err));
    },
    onFileChange(event) {
      this.newAudiobook.coverFile = event.target.files[0];
    },
    async uploadCover() {
      if (!this.newAudiobook.coverFile) return null;
      const formData = new FormData();
      formData.append("cover", this.newAudiobook.coverFile);
      try {
        const res = await axios.post(`${backendUrl}/upload-cover`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        return res.data.cover_path;
      } catch (err) {
        console.error("Error uploading cover:", err);
        return null;
      }
    },
    async downloadAudiobook() {
      const coverPath = await this.uploadCover();
      axios.post(`${backendUrl}/download-audiobook`, {
        ...this.newAudiobook,
        cover_path: coverPath,
      }).then(() => {
        console.log("Audiobook downloaded.");
        this.getAudiobooks();
      }).catch((err) => console.error(err));
    },
  },
  created() {
    this.getAudiobooks();
    this.getCreativeTonies();
  },
};
</script>