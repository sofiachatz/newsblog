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

function reply(cId) {
  const parent_id = document.getElementsByName("parent_id");
    for (let i = 0; i < parent_id.length; i++) {
      parent_id[i].value = cId;
    }
}
