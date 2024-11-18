<template>
  <main role="main">
    <div class="album py-5 bg-light">
      <div class="container">
        <h2 class="mb-4">Download a New Audiobook</h2>
        <form @submit.prevent="downloadAudiobook">
          <div class="form-group">
            <label for="url">YouTube URL</label>
            <input
              type="text"
              id="url"
              class="form-control"
              v-model="newAudiobook.url"
              placeholder="Enter YouTube URL"
              required
            />
          </div>
          <div class="form-group">
            <label for="title">Title</label>
            <input
              type="text"
              id="title"
              class="form-control"
              v-model="newAudiobook.title"
              placeholder="Enter Title"
              required
            />
          </div>
          <div class="form-group">
            <label for="artist">Artist</label>
            <input
              type="text"
              id="artist"
              class="form-control"
              v-model="newAudiobook.artist"
              placeholder="Enter Artist"
              required
            />
          </div>
          <div class="form-group">
            <label for="album">Album</label>
            <input
              type="text"
              id="album"
              class="form-control"
              v-model="newAudiobook.album"
              placeholder="Enter Album"
              required
            />
          </div>
          <div class="form-group">
            <label for="cover">Cover Image</label>
            <input
              type="file"
              id="cover"
              class="form-control"
              @change="onFileChange"
            />
          </div>
          <button type="submit" class="btn btn-primary">Download Audiobook</button>
        </form>

        <hr />

        <h2 class="mb-4">Available Audiobooks</h2>
        <div class="row">
          <div v-for="audiobook in audiobooks" :key="audiobook.id" class="col-md-3">
            <div class="card mb-4 shadow-sm">
              <div v-if="audiobook.cover_uri !== null">
                <img :src="'./assets/covers/' + audiobook.cover_uri"
                     class="card-img-top"
                     :alt="audiobook.title">
              </div>
              <div v-else>
                <svg class="bd-placeholder-img card-img-top" width="100%" height="253"
                     xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice"
                     focusable="false" role="img" aria-label="Placeholder: Thumbnail">
                  <title>no cover</title>
                  <rect width="100%" height="100%" fill="#55595c"/>
                  <text x="50%" y="50%" fill="#eceeef" dy=".3em">no cover</text>
                </svg>
              </div>
              <div class="card-body">
                <h5 class="card-title">
                  {{ audiobook.title }}
                  <div v-if="audiobook.disc !== null"> ({{ audiobook.disc }})</div>
                </h5>
                <h6 class="card-subtitle mb-2 text-muted">{{ audiobook.artist }}</h6>
              </div>
              <Tonies :tonies="creativetonies"
                      :audiobookID="audiobook.id"
                      @onchange="uploadAlbumToTonie"/>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script>
import axios from 'axios';
import Tonies from './Tonies.vue';

const backendUrl = `${process.env.VUE_APP_BACKEND_SCHEME}://${process.env.VUE_APP_BACKEND_HOST}:${process.env.VUE_APP_BACKEND_PORT}`;

export default {
  components: { Tonies },
  data() {
    return {
      audiobooks: [],
      creativetonies: [],
      newAudiobook: {
        url: '',
        title: '',
        artist: '',
        album: '',
        coverFile: null,
      },
    };
  },
  methods: {
    getAudiobooks() {
      const path = `${backendUrl}/audiobooks`;
      axios.get(path)
        .then((res) => {
          this.audiobooks = res.data.audiobooks;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    getCreativeTonies() {
      const path = `${backendUrl}/creativetonies`;
      axios.get(path)
        .then((res) => {
          this.creativetonies = res.data.creativetonies;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    uploadAlbumToTonie(tonieID, audiobookID) {
      const path = `${backendUrl}/upload`;
      axios.post(path, { tonie_id: tonieID, audiobook_id: audiobookID })
        .then((res) => {
          console.log('Upload id: ' + res.data.upload_id);
        })
        .catch((error) => {
          console.error(error);
        });
    },
    onFileChange(event) {
      this.newAudiobook.coverFile = event.target.files[0];
    },
    async uploadCover() {
      if (this.newAudiobook.coverFile) {
        const formData = new FormData();
        formData.append('cover', this.newAudiobook.coverFile);
        const path = `${backendUrl}/upload-cover`;

        try {
          const res = await axios.post(path, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
          });
          return res.data.cover_path;
        } catch (error) {
          console.error('Error uploading cover:', error);
        }
      }
      return null;
    },
    async downloadAudiobook() {
      const coverPath = await this.uploadCover();
      const path = `${backendUrl}/download-audiobook`;

      axios.post(path, {
        url: this.newAudiobook.url,
        title: this.newAudiobook.title,
        artist: this.newAudiobook.artist,
        album: this.newAudiobook.album,
        cover_path: coverPath,
      })
        .then((res) => {
          console.log('Audiobook downloaded:', res.data);
          this.getAudiobooks(); // Refresh audiobooks
        })
        .catch((error) => {
          console.error('Error downloading audiobook:', error);
        });
    },
  },
  created() {
    this.getAudiobooks();
    this.getCreativeTonies();
  },
};
</script>