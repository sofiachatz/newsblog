function like(postId) {
    const likeCount = document.getElementById(`likes-count-${postId}`);
    const likeButton = document.getElementById(`like-button-${postId}`);
  
    fetch(`/like_post/${postId}`, { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        likeCount.innerHTML = data["likes"];
        if (data["liked"] === true) {
          likeButton.className = "fa-solid fa-heart";
        } else {
          likeButton.className = "fa-regular fa-heart";
        }
      })
      .catch((e) => alert("Login to like posts."));
}

  function likePost(postId) {
    const likeCount = document.getElementById(`likes-cnt-${postId}`);
    const likeButton = document.getElementById(`like-btn-${postId}`);
  
    fetch(`/like_post/${postId}`, { method: "POST" })
      .then((res) => res.json())
      .then((data) => {
        likeCount.innerHTML = data["likes"];
        if (data["liked"] === true) {
          likeButton.className = "fa-solid fa-heart fa-2xl";
        } else {
          likeButton.className = "fa-regular fa-heart fa-2xl";
        }
      })
      .catch((e) => alert("Login to like posts."));
}

function like_comm(cId) {
  const likecommCount = document.getElementById(`likes-comm-count-${cId}`);
  const likecommButton = document.getElementById(`like-comm-btn-${cId}`);
  
  fetch(`/like_comment/${cId}`, { method: "POST" })
    .then((res) => res.json())
    .then((data) => {
      likecommCount.innerHTML = data["likes"];
      if (data["liked"] === true) {
        likecommButton.className = "fa-solid fa-heart";
      } else {
        likecommButton.className = "fa-regular fa-heart";
      }
    })
    .catch((e) => alert("Login to like comments."));
}


function reply(cId) {
  const parent_id = document.getElementsByName("parent_id");
    for (let i = 0; i < parent_id.length; i++) {
      parent_id[i].value = cId;
    }
}
