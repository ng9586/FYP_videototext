import streamlit as st
import yt_dlp as youtube_dl
import requests
import pprint
from configure import auth_key
from time import sleep

if 'status' not in st.session_state:
    st.session_state['status'] = 'submitted'

ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'ffmpeg-location': './',
    'outtmpl': "./%(id)s.%(ext)s",
    'verbose': True,  # For more detailed output
}

transcript_endpoint = "https://api.assemblyai.com/v2/transcript"
upload_endpoint = 'https://api.assemblyai.com/v2/upload'

headers_auth_only = {'authorization': auth_key}
headers = {
    "authorization": auth_key,
    "content-type": "application/json"
}
CHUNK_SIZE = 5242880

@st.cache_data
def transcribe_from_link(link, categories: bool):
    _id = link.strip()

    def get_vid(_id):
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(_id)
        except youtube_dl.utils.DownloadError as e:
            print(f"Error downloading video: {e}")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None

    # download the audio of the YouTube video locally
    meta = get_vid(_id)
    if meta is None:
        print("Failed to retrieve video metadata.")
        return None

    save_location = meta['id'] + ".mp3"

    print('Saved mp3 to', save_location)

    def read_file(filename):
        with open(filename, 'rb') as _file:
            while True:
                data = _file.read(CHUNK_SIZE)
                if not data:
                    break
                yield data

    # upload audio file to AssemblyAI
    upload_response = requests.post(
        upload_endpoint,
        headers=headers_auth_only, data=read_file(save_location)
    )

    audio_url = upload_response.json()['upload_url']
    print('Uploaded to', audio_url)

    # start the transcription of the audio file
    transcript_request = {
        'audio_url': audio_url,
        'iab_categories': 'True' if categories else 'False',
    }

    transcript_response = requests.post(transcript_endpoint, json=transcript_request, headers=headers)

    # this is the id of the file that is being transcribed in the AssemblyAI servers
    # we will use this id to access the completed transcription
    transcript_id = transcript_response.json()['id']
    polling_endpoint = transcript_endpoint + "/" + transcript_id

    print("Transcribing at", polling_endpoint)

    return polling_endpoint

def get_status(polling_endpoint):
    polling_response = requests.get(polling_endpoint, headers=headers)
    st.session_state['status'] = polling_response.json()['status']

def refresh_state():
    st.session_state['status'] = 'submitted'

def translate_text(text, target_language, api_key):
    # 使用Google Translate API進行翻譯
    url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"
    data = {
        "q": text,
        "target": target_language
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        return response.json()['data']['translations'][0]['translatedText']
    else:
        return "翻譯失敗"

st.title('Easily transcribe YouTube videos')

link = st.text_input('Enter your YouTube video link', 'https://youtu.be/dccdadl90vs', on_change=refresh_state)
st.video(link)

st.text("The transcription is " + st.session_state['status'])

polling_endpoint = transcribe_from_link(link, False)

if polling_endpoint is not None:
    st.button('Get Status', on_click=get_status, args=(polling_endpoint,))
else:
    st.error("Failed to start transcription.")

transcript = ''
if st.session_state['status'] == 'completed':
    polling_response = requests.get(polling_endpoint, headers=headers)
    transcript = polling_response.json()['text']

    st.markdown(transcript)

    # 添加翻譯選擇功能
    languages = {
        "Chinese (Traditional)": "zh-TW",
        "Japanese": "ja",
        "Korean": "ko",
        "Spanish": "es",
        # 添加更多語言選擇
    }
    
    selected_language = st.selectbox("Select Translation Language", list(languages.keys()))

    if st.button('Translate'):
        api_key = "your-api-key-here"  # 將這裡替換為你的Google Cloud Translation API key
        translated_text = translate_text(transcript, languages[selected_language], api_key)
        st.markdown(f"### Translated Text ({selected_language}):")
        st.markdown(translated_text)
