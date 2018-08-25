$(function(){
// Homepage | section.blog | article nav behavior
  
  // first, hide everything except 2018 posts be default
  $(".article-item:not(.article-2018)").removeClass("show");

  // if click on All, show all posts
  $("#articlesAllTrigger").on("click", function(event){
    event.preventDefault();
    $(".article-nav .year").removeClass("showing");
    $(this).addClass("showing");
    $(".article-item").addClass("show");
  });

  // if click on 2018, show 2018 posts
  $("#articles2018Trigger").on("click", function(event){
    event.preventDefault();
    $(".article-nav .year").removeClass("showing");
    $(this).addClass("showing");
    $(".article-item").removeClass("show");
    $(".article-item.article-2018").addClass("show");
  });

  // if click on 2017, show 2017 posts
  $("#articles2017Trigger").on("click", function(event){
    event.preventDefault();
    $(".article-nav .year").removeClass("showing");
    $(this).addClass("showing");
    $(".article-item").removeClass("show");
    $(".article-item.article-2017").addClass("show");
  });
});
