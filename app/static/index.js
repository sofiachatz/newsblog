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

function set_notification_count(n) {
  const count = document.getElementById('notification_count');
  count.innerText = n;
  count.style.visibility = n ? 'visible' : 'hidden';
}


document.addEventListener("DOMContentLoaded", function() {
  const urlParams = new URLSearchParams(window.location.search);
  const anchor = window.location.hash.substring(1);
  if (anchor) {
      const targetElement = document.getElementById(anchor);
      if (targetElement) {
          if (anchor.startsWith('reply-')) {
              const reply = document.getElementById(anchor);
              if (reply) {
                  const parentCommentId = reply.closest('.collapse').id.replace('replies-', '');
                  const parentCollapse = document.getElementById('replies-' + parentCommentId);
                  const parentToggle = document.querySelector(`[href="#replies-${parentCommentId}"]`);
                  if (parentCollapse && parentToggle) {
                      parentCollapse.classList.add('show');
                      parentCollapse.addEventListener('shown.bs.collapse', function () {
                          reply.scrollIntoView({ behavior: 'smooth' });
                      });
                  }
              }
          } else {
              targetElement.scrollIntoView({ behavior: 'smooth' });
          }
      }
  }
});